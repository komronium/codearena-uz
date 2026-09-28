"""SQL problems: 10 beginner, 10 easy, 5 medium, 3 hard, over three small databases
(a university, a shop, a company).

Each problem has a sample data set, shown on its page with the expected result, and a
bigger hidden check data set from another random seed, so a query that spells out the
shown answer fails. Expected results come from the reference query run by the judge
itself (judge.sql_judge), never typed by hand. Every problem also lists near-miss
queries (a forgotten WHERE, GROUP BY or tie-break) that must fail on its data: the
command refuses to save a problem whose data can't tell them apart from the answer.

Re-running is safe: problems are matched by slug, their data rebuilt.
"""
import random
from dataclasses import dataclass, field

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.problems.models import Problem, SQLDataset, Tag
from judge import sql_judge

D = Problem.Difficulty

FIRST = ["Aziz", "Anvar", "Aziza", "Akmal", "Alisher", "Bekzod", "Bobur", "Dilnoza", "Doniyor", "Elyor",
         "Farrux", "Gulnora", "Hamid", "Ilhom", "Jasur", "Kamola", "Laylo", "Madina", "Nodir", "Otabek",
         "Rustam", "Sardor", "Sevara", "Shahzod", "Temur", "Umida", "Vali", "Zarina", "Nilufar", "Yusuf"]
LAST = ["Karimov", "Rahimov", "Toshmatov", "Aliyev", "Qodirov", "Yusupov", "Ergashev", "Nazarov",
        "Sobirov", "Umarov", "Xolmatov", "Mirzayev"]
CITIES = ["Toshkent", "Samarqand", "Buxoro", "Andijon", "Namangan", "Xiva", "Nukus", "Qarshi"]
GROUPS = ["IT-21", "IT-22", "MT-21", "FL-22"]
COURSES = ["Algoritmlar", "SQL asoslari", "Python", "Diskret matematika", "Fizika", "Ingliz tili",
           "Web dasturlash", "Tarix"]
PRODUCTS = {
    "Elektronika": ["Telefon", "Noutbuk", "Quloqchin", "Planshet", "Aqlli soat", "Kamera"],
    "Kitoblar": ["Sariq devni minib", "Mehrobdan chayon", "Kecha va kunduz", "Shaytanat", "Alkimyogar"],
    "Kiyim": ["Kurtka", "Futbolka", "Shim", "Krossovka", "Shapka"],
    "Oziq-ovqat": ["Non", "Sut", "Asal", "Choy", "Qahva", "Guruch"],
    "Sport": ["Koptok", "Gantel", "Velosiped", "Raketka", "Arqon"],
}
DEPARTMENTS = ["IT", "Moliya", "Marketing", "Kadrlar", "Savdo"]

SCHEMA = {
    "students": "CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, group_name TEXT, city TEXT, "
                "birth_year INTEGER, score INTEGER);",
    "courses": "CREATE TABLE courses (id INTEGER PRIMARY KEY, title TEXT, credits INTEGER);",
    "enrollments": "CREATE TABLE enrollments (student_id INTEGER, course_id INTEGER, grade INTEGER);",
    "customers": "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT, phone TEXT);",
    "products": "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category TEXT, price INTEGER, "
                "stock INTEGER);",
    "orders": "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT);",
    "order_items": "CREATE TABLE order_items (order_id INTEGER, product_id INTEGER, quantity INTEGER);",
    "departments": "CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT);",
    "employees": "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, department_id INTEGER, "
                 "manager_id INTEGER, salary INTEGER, hire_date TEXT);",
}


def _people(rng: random.Random, n: int) -> list[str]:
    return rng.sample([f"{f} {s}" for f in FIRST for s in LAST], n)


def _date(rng: random.Random, year: int = 2025) -> str:
    return f"{year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


def university(rng: random.Random, big: bool) -> dict[str, list[tuple]]:
    n = 60 if big else 10
    # the boundary scores of the tasks come up in every data set: 85 vs "85 and up", 86/71/56 for the grades
    scores = [85, 86, 71, 56, 70] + [rng.randint(40, 100) for _ in range(n - 5)]
    rng.shuffle(scores)
    students = [(i + 1, name, rng.choice(GROUPS[:4 if big else 3]), rng.choice(CITIES[:8 if big else 4]),
                 rng.randint(2001, 2007), score) for i, (name, score) in enumerate(zip(_people(rng, n), scores))]
    titles = COURSES if big else COURSES[:4]
    courses = [(i + 1, t, rng.choice([3, 4, 5, 6])) for i, t in enumerate(titles)]
    taken = [c[0] for c in courses[:-1]]  # nobody takes the last course: LEFT JOIN has a zero to keep
    enrollments = [(s[0], c, rng.randint(2, 5)) for s in students for c in rng.sample(taken, rng.randint(1, 3))]
    return {"students": students, "courses": courses, "enrollments": enrollments}


def shop(rng: random.Random, big: bool) -> dict[str, list[tuple]]:
    n_customers, n_orders = (30, 140) if big else (7, 14)
    customers = [(i + 1, name, rng.choice(CITIES[:6 if big else 3]),
                  None if rng.random() < 0.25 else f"+99890{rng.randint(1000000, 9999999)}")
                 for i, name in enumerate(_people(rng, n_customers))]
    catalog = [(cat, name) for cat, names in PRODUCTS.items() for name in names]
    picked = catalog if big else rng.sample(catalog, 9)
    products = [(i + 1, name, cat, rng.randrange(5_000, 3_000_000, 5_000), rng.randint(0, 120))
                for i, (cat, name) in enumerate(picked)]
    buyers = [c[0] for c in customers[: max(2, int(n_customers * 0.75))]]  # the rest never ordered
    dates = []
    for c in buyers[:3 if big else 1]:  # a run of three days in a row
        start = rng.randint(1, 25)
        dates += [(c, f"2025-03-{d:02d}") for d in range(start, start + 3)]
    for c in buyers[3:5] if big else buyers[1:2]:  # two days in a row only: a near miss
        start = rng.randint(1, 25)
        dates += [(c, f"2025-06-{d:02d}") for d in (start, start + 1)]
    while len(dates) < n_orders:
        dates.append((rng.choice(buyers), _date(rng)))
    orders = [(i + 1, c, d) for i, (c, d) in enumerate(dates)]
    items = [(o[0], p[0], rng.randint(1, 5)) for o in orders for p in rng.sample(products, rng.randint(1, 3))]
    return {"customers": customers, "products": products, "orders": orders, "order_items": items}


def company(rng: random.Random, big: bool) -> dict[str, list[tuple]]:
    names = DEPARTMENTS if big else DEPARTMENTS[:3]
    departments = [(i + 1, name) for i, name in enumerate(names)]
    people = _people(rng, 50 if big else 11)
    employees, heads = [], {}
    for i, name in enumerate(people):
        dept = departments[i % len(departments)][0]
        salary = rng.randrange(4_000_000, 20_000_000, 500_000)
        manager = heads.get(dept)
        if manager is None:
            heads[dept] = i + 1
        employees.append((i + 1, name, dept, manager, salary, _date(rng, rng.randint(2018, 2025))))
    # a tie for the top salary in the first department: "all of them", not "one of them"
    first = [e for e in employees if e[2] == 1]
    top = max(e[4] for e in first)
    employees = [(e[0], e[1], e[2], e[3], top, e[5]) if e[0] == first[-1][0] else e for e in employees]
    return {"departments": departments, "employees": employees}


THEMES = {"university": university, "shop": shop, "company": company}


def _literal(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def dump(data: dict[str, list[tuple]], tables: list[str]) -> tuple[str, str]:
    schema = "\n".join(SCHEMA[t] for t in tables)
    seed = "\n".join(f"INSERT INTO {t} VALUES\n" + ",\n".join(
        "(" + ", ".join(_literal(v) for v in row) + ")" for row in data[t]) + ";" for t in tables)
    return schema, seed


@dataclass
class Spec:
    slug: str
    title: str
    statement: str
    output: str           # the columns wanted, in order
    theme: str
    tables: list[str]
    solution: str
    difficulty: str
    tags: list[str]
    wrong: list[str] = field(default_factory=list)  # near misses the data must reject
    ordered: bool = False


SPECS: list[Spec] = [
    # ---- beginner -----------------------------------------------------------
    Spec("sql-talabalar-royxati", "Talabalar ro‘yxati",
         "Universitet bazasida `students` jadvali bor. Barcha talabalarning ismi va shahrini chiqaring.",
         "Ikki ustun: `name`, `city`.", "university", ["students"],
         "SELECT name, city FROM students", D.BEGINNER, ["select"],
         wrong=["SELECT city, name FROM students", "SELECT name FROM students"]),
    Spec("sql-toshkentlik-talabalar", "Toshkentlik talabalar",
         "Shahri `Toshkent` bo‘lgan talabalarning ismlarini chiqaring.",
         "Bitta ustun: `name`.", "university", ["students"],
         "SELECT name FROM students WHERE city = 'Toshkent'", D.BEGINNER, ["select", "where"],
         wrong=["SELECT name FROM students"]),
    Spec("sql-alochi-talabalar", "A’lochilar",
         "Bali **85 va undan yuqori** bo‘lgan talabalarning ismi va balini chiqaring.",
         "Ikki ustun: `name`, `score`.", "university", ["students"],
         "SELECT name, score FROM students WHERE score >= 85", D.BEGINNER, ["where"],
         wrong=["SELECT name, score FROM students WHERE score > 85", "SELECT name, score FROM students"]),
    Spec("sql-tugilgan-yillar", "2003–2005 yilda tug‘ilganlar",
         "2003 yildan 2005 yilgacha (ikkala yil ham kiradi) tug‘ilgan talabalarning ismi va tug‘ilgan yilini "
         "chiqaring.",
         "Ikki ustun: `name`, `birth_year`.", "university", ["students"],
         "SELECT name, birth_year FROM students WHERE birth_year BETWEEN 2003 AND 2005", D.BEGINNER, ["where"],
         wrong=["SELECT name, birth_year FROM students WHERE birth_year > 2003 AND birth_year < 2005"]),
    Spec("sql-narx-boyicha-tartib", "Arzonidan qimmatiga",
         "Do‘kondagi mahsulotlar nomi va narxini narx bo‘yicha **o‘sish** tartibida chiqaring. Narxi teng "
         "mahsulotlar nomi bo‘yicha alifbo tartibida tursin.",
         "Ikki ustun: `name`, `price`. Tartib muhim.", "shop", ["products"],
         "SELECT name, price FROM products ORDER BY price, name", D.BEGINNER, ["order-by"],
         wrong=["SELECT name, price FROM products ORDER BY price DESC, name", "SELECT name, price FROM products"],
         ordered=True),
    Spec("sql-eng-qimmat-uchta", "Eng qimmat uchta mahsulot",
         "Eng qimmat **uchta** mahsulotning nomi va narxini chiqaring: avval eng qimmati. Narxi teng bo‘lsa, "
         "nomi alifbo bo‘yicha oldinroq kelgani oldin.",
         "Ikki ustun: `name`, `price`. Tartib muhim.", "shop", ["products"],
         "SELECT name, price FROM products ORDER BY price DESC, name LIMIT 3", D.BEGINNER, ["order-by", "limit"],
         wrong=["SELECT name, price FROM products ORDER BY price DESC, name",
                "SELECT name, price FROM products ORDER BY price, name LIMIT 3"], ordered=True),
    Spec("sql-mijozlar-shaharlari", "Mijozlar qaysi shaharlardan",
         "Mijozlar yashaydigan shaharlarni chiqaring, har bir shahar **bir marta**.",
         "Bitta ustun: `city`.", "shop", ["customers"],
         "SELECT DISTINCT city FROM customers", D.BEGINNER, ["distinct"],
         wrong=["SELECT city FROM customers"]),
    Spec("sql-a-harfli-ismlar", "A harfidan boshlanadigan ismlar",
         "Ismi `A` harfi bilan boshlanadigan talabalarning to‘liq ismini (`name`) chiqaring.\n\n"
         "Maslahat: `LIKE` va `%` belgisi.",
         "Bitta ustun: `name`.", "university", ["students"],
         "SELECT name FROM students WHERE name LIKE 'A%'", D.BEGINNER, ["where", "like"],
         wrong=["SELECT name FROM students WHERE name LIKE '%A%'", "SELECT name FROM students"]),
    Spec("sql-telefonsiz-mijozlar", "Telefoni yozilmagan mijozlar",
         "Ba’zi mijozlarning telefon raqami ma’lum emas (`phone` ustunida `NULL`). Shunday mijozlarning "
         "ismlarini chiqaring.\n\nEslatma: `NULL` bilan `=` ishlamaydi.",
         "Bitta ustun: `name`.", "shop", ["customers"],
         "SELECT name FROM customers WHERE phone IS NULL", D.BEGINNER, ["null-values", "where"],
         wrong=["SELECT name FROM customers WHERE phone IS NOT NULL"]),
    Spec("sql-ombordagi-qiymat", "Ombordagi tovar qiymati",
         "Har bir mahsulot uchun uning nomini va omborda turgan tovarning umumiy qiymatini (`price * stock`) "
         "chiqaring.",
         "Ikki ustun: `name`, `total_value`.", "shop", ["products"],
         "SELECT name, price * stock AS total_value FROM products", D.BEGINNER, ["select"],
         wrong=["SELECT name, price FROM products", "SELECT name, price + stock FROM products"]),

    # ---- easy ---------------------------------------------------------------
    Spec("sql-shahar-boyicha-talabalar", "Har bir shahardan nechta talaba",
         "Har bir shahar uchun u yerdan kelgan talabalar sonini chiqaring.",
         "Ikki ustun: `city`, `students_count`.", "university", ["students"],
         "SELECT city, COUNT(*) AS students_count FROM students GROUP BY city", D.EASY, ["group-by", "aggregation"],
         wrong=["SELECT city, COUNT(DISTINCT group_name) FROM students GROUP BY city"]),
    Spec("sql-guruh-ortacha-bali", "Guruhlarning o‘rtacha bali",
         "Har bir guruh (`group_name`) uchun talabalarining o‘rtacha balini **2 xonagacha yaxlitlab** "
         "(`ROUND(..., 2)`) chiqaring.",
         "Ikki ustun: `group_name`, `avg_score`.", "university", ["students"],
         "SELECT group_name, ROUND(AVG(score), 2) AS avg_score FROM students GROUP BY group_name", D.EASY,
         ["group-by", "aggregation"],
         wrong=["SELECT group_name, AVG(score) FROM students GROUP BY group_name",
                "SELECT group_name, ROUND(AVG(score)) FROM students GROUP BY group_name"]),
    Spec("sql-kategoriya-narxlari", "Kategoriyadagi narxlar oralig‘i",
         "Har bir kategoriya uchun eng arzon va eng qimmat mahsulot narxini chiqaring.",
         "Uch ustun: `category`, `min_price`, `max_price`.", "shop", ["products"],
         "SELECT category, MIN(price) AS min_price, MAX(price) AS max_price FROM products GROUP BY category",
         D.EASY, ["group-by", "aggregation"],
         wrong=["SELECT category, MAX(price), MIN(price) FROM products GROUP BY category"]),
    Spec("sql-ombor-hisoboti", "Ombor hisoboti",
         "Bitta qatorda: mahsulotlar soni, ombordagi jami dona (`stock` yig‘indisi) va o‘rtacha narx "
         "(2 xonagacha yaxlitlangan).",
         "Uch ustun: `products_count`, `total_stock`, `avg_price`.", "shop", ["products"],
         "SELECT COUNT(*) AS products_count, SUM(stock) AS total_stock, ROUND(AVG(price), 2) AS avg_price "
         "FROM products", D.EASY, ["aggregation"],
         wrong=["SELECT COUNT(*), COUNT(stock), ROUND(AVG(price), 2) FROM products"]),
    Spec("sql-yaxshi-guruhlar", "O‘rtacha bali 70 dan yuqori guruhlar",
         "O‘rtacha bali **70 dan katta** bo‘lgan guruhlarni va ulardagi talabalar sonini chiqaring.\n\n"
         "Maslahat: guruhlangan natijani `HAVING` bilan saralang.",
         "Ikki ustun: `group_name`, `students_count`.", "university", ["students"],
         "SELECT group_name, COUNT(*) AS students_count FROM students GROUP BY group_name HAVING AVG(score) > 70",
         D.EASY, ["group-by", "having"],
         wrong=["SELECT group_name, COUNT(*) FROM students GROUP BY group_name",
                "SELECT group_name, COUNT(*) FROM students WHERE score > 70 GROUP BY group_name"]),
    Spec("sql-buyurtma-egalari", "Buyurtma kimniki",
         "Har bir buyurtma uchun uning raqamini (`orders.id`), sanasini va buyurtma bergan mijozning ismini "
         "chiqaring.",
         "Uch ustun: `order_id`, `order_date`, `customer_name`.", "shop", ["customers", "orders"],
         "SELECT o.id AS order_id, o.order_date, c.name AS customer_name FROM orders o "
         "JOIN customers c ON c.id = o.customer_id", D.EASY, ["join"],
         wrong=["SELECT o.id, o.order_date, c.name FROM orders o JOIN customers c ON c.id = o.id"]),
    Spec("sql-xodimlar-bolimlari", "Xodim qaysi bo‘limda",
         "Har bir xodimning ismini va u ishlaydigan bo‘lim nomini chiqaring.",
         "Ikki ustun: `employee`, `department`.", "company", ["departments", "employees"],
         "SELECT e.name AS employee, d.name AS department FROM employees e "
         "JOIN departments d ON d.id = e.department_id",
         D.EASY, ["join"],
         wrong=["SELECT e.name, d.name FROM employees e JOIN departments d ON d.id = e.id"]),
    Spec("sql-baho-harfi", "Harfli baho",
         "Har bir talaba uchun ismi va harfli bahosini chiqaring: bali 86 va undan yuqori — `A`, 71–85 — `B`, "
         "56–70 — `C`, qolganlar — `F`.",
         "Ikki ustun: `name`, `grade`.", "university", ["students"],
         "SELECT name, CASE WHEN score >= 86 THEN 'A' WHEN score >= 71 THEN 'B' WHEN score >= 56 THEN 'C' "
         "ELSE 'F' END AS grade FROM students", D.EASY, ["case-when"],
         wrong=["SELECT name, CASE WHEN score > 86 THEN 'A' WHEN score > 71 THEN 'B' WHEN score > 56 THEN 'C' "
                "ELSE 'F' END FROM students"]),
    Spec("sql-yil-boyicha-yollanganlar", "Har yili nechta xodim ishga olingan",
         "`hire_date` ustunida ishga olingan sana `YYYY-MM-DD` ko‘rinishida saqlanadi. Har bir yil uchun "
         "o‘sha yili ishga olingan xodimlar sonini chiqaring.\n\n"
         "Maslahat: `strftime('%Y', hire_date)` yoki `substr(hire_date, 1, 4)` — yilni ajratadi (matn bo‘lib).",
         "Ikki ustun: `year` (matn, masalan `2021`), `hired`.", "company", ["employees"],
         "SELECT strftime('%Y', hire_date) AS year, COUNT(*) AS hired FROM employees GROUP BY year", D.EASY,
         ["date-functions", "group-by"],
         wrong=["SELECT hire_date, COUNT(*) FROM employees GROUP BY hire_date"]),
    Spec("sql-ism-uzunligi", "Katta harflar va uzunlik",
         "Har bir mijoz uchun ismini **katta harflarda** va ismidagi belgilar sonini chiqaring "
         "(`UPPER`, `LENGTH`).",
         "Ikki ustun: `name_upper`, `name_length`.", "shop", ["customers"],
         "SELECT UPPER(name) AS name_upper, LENGTH(name) AS name_length FROM customers", D.EASY,
         ["string-functions"],
         wrong=["SELECT name, LENGTH(name) FROM customers", "SELECT UPPER(name), LENGTH(city) FROM customers"]),

    # ---- medium -------------------------------------------------------------
    Spec("sql-ortachadan-yuqori-maosh", "O‘rtachadan ko‘p oluvchilar",
         "Maoshi kompaniya bo‘yicha **o‘rtacha maoshdan katta** bo‘lgan xodimlarning ismi va maoshini "
         "chiqaring.\n\nO‘rtacha maoshni qo‘lda yozmang: yashirin ma’lumotlarda u boshqacha. Ichki so‘rov "
         "(subquery) ishlating.",
         "Ikki ustun: `name`, `salary`.", "company", ["employees"],
         "SELECT name, salary FROM employees WHERE salary > (SELECT AVG(salary) FROM employees)", D.MEDIUM,
         ["subquery"],
         wrong=["SELECT name, salary FROM employees WHERE salary >= (SELECT MIN(salary) FROM employees)"]),
    Spec("sql-buyurtmasiz-mijozlar", "Hech narsa olmagan mijozlar",
         "Birorta ham buyurtma bermagan mijozlarning ismlarini chiqaring.",
         "Bitta ustun: `name`.", "shop", ["customers", "orders"],
         "SELECT name FROM customers WHERE id NOT IN (SELECT customer_id FROM orders)", D.MEDIUM,
         ["subquery", "left-join"],
         wrong=["SELECT DISTINCT c.name FROM customers c JOIN orders o ON o.customer_id = c.id"]),
    Spec("sql-mijozlar-xarajati", "Kim qancha xarid qildi",
         "Har bir buyurtma bir nechta mahsulotdan iborat (`order_items`: qaysi mahsulotdan necha dona). "
         "Buyurtma bergan har bir mijoz uchun jami xarid summasini (`quantity * price` yig‘indisi) toping.\n\n"
         "Natijani summa bo‘yicha **kamayish** tartibida chiqaring; summa teng bo‘lsa — ism bo‘yicha alifbo "
         "tartibida.",
         "Ikki ustun: `name`, `total`. Tartib muhim.", "shop", ["customers", "products", "orders", "order_items"],
         "SELECT c.name, SUM(oi.quantity * p.price) AS total FROM customers c "
         "JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id "
         "JOIN products p ON p.id = oi.product_id GROUP BY c.id, c.name ORDER BY total DESC, c.name",
         D.MEDIUM, ["join", "group-by", "order-by"],
         wrong=["SELECT c.name, SUM(p.price) AS total FROM customers c JOIN orders o ON o.customer_id = c.id "
                "JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id "
                "GROUP BY c.id ORDER BY total DESC, c.name",
                "SELECT c.name, SUM(oi.quantity * p.price) AS total FROM customers c "
                "JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id "
                "JOIN products p ON p.id = oi.product_id GROUP BY c.id ORDER BY total, c.name"],
         ordered=True),
    Spec("sql-bolim-rekordchilari", "Bo‘limdagi eng katta maosh",
         "Har bir bo‘limda eng katta maosh oladigan xodim(lar)ni toping: bo‘lim nomi, xodim ismi va maoshi. "
         "Bo‘limda eng katta maoshni bir nechta xodim olsa, hammasini chiqaring.",
         "Uch ustun: `department`, `employee`, `salary`.", "company", ["departments", "employees"],
         "SELECT d.name AS department, e.name AS employee, e.salary FROM employees e "
         "JOIN departments d ON d.id = e.department_id "
         "WHERE e.salary = (SELECT MAX(salary) FROM employees x WHERE x.department_id = e.department_id)",
         D.MEDIUM, ["subquery", "join"],
         wrong=["SELECT d.name, e.name, e.salary FROM employees e JOIN departments d ON d.id = e.department_id "
                "WHERE e.salary = (SELECT MAX(salary) FROM employees)",
                "SELECT d.name, e.name, MAX(e.salary) FROM employees e "
                "JOIN departments d ON d.id = e.department_id GROUP BY d.id"]),
    Spec("sql-kurslar-talabalar-soni", "Har bir kursga nechta talaba yozilgan",
         "Har bir kurs nomi va unga yozilgan talabalar sonini chiqaring. Hech kim yozilmagan kurslar ham "
         "`0` bilan chiqsin.",
         "Ikki ustun: `title`, `students_count`.", "university", ["courses", "enrollments"],
         "SELECT c.title, COUNT(e.student_id) AS students_count FROM courses c "
         "LEFT JOIN enrollments e ON e.course_id = c.id GROUP BY c.id, c.title", D.MEDIUM,
         ["left-join", "group-by"],
         wrong=["SELECT c.title, COUNT(*) FROM courses c JOIN enrollments e ON e.course_id = c.id GROUP BY c.id",
                "SELECT c.title, COUNT(*) FROM courses c LEFT JOIN enrollments e ON e.course_id = c.id "
                "GROUP BY c.id"]),

    # ---- hard ---------------------------------------------------------------
    Spec("sql-bolimdagi-top-2", "Bo‘limdagi ikki eng katta maosh",
         "Har bir bo‘limda maoshlarni kattasidan boshlab qo‘yamiz. Maoshi bo‘limdagi **eng katta ikkita har "
         "xil** maoshdan biriga teng bo‘lgan xodimlarni chiqaring: bo‘lim nomi, xodim ismi, maoshi.\n\n"
         "Masalan, bo‘limda maoshlar 9, 9, 7, 5 bo‘lsa — 9, 9 va 7 oladiganlar chiqadi.\n\n"
         "Maslahat: oyna funksiyalari — `DENSE_RANK() OVER (PARTITION BY ... ORDER BY ...)`.",
         "Uch ustun: `department`, `employee`, `salary`.", "company", ["departments", "employees"],
         "SELECT department, employee, salary FROM (SELECT d.name AS department, e.name AS employee, e.salary, "
         "DENSE_RANK() OVER (PARTITION BY e.department_id ORDER BY e.salary DESC) AS rnk FROM employees e "
         "JOIN departments d ON d.id = e.department_id) WHERE rnk <= 2", D.HARD, ["window-functions", "join"],
         wrong=["SELECT department, employee, salary FROM (SELECT d.name AS department, e.name AS employee, "
                "e.salary, ROW_NUMBER() OVER (PARTITION BY e.department_id ORDER BY e.salary DESC) AS rnk "
                "FROM employees e JOIN departments d ON d.id = e.department_id) WHERE rnk <= 2",
                "SELECT department, employee, salary FROM (SELECT d.name AS department, e.name AS employee, "
                "e.salary, DENSE_RANK() OVER (ORDER BY e.salary DESC) AS rnk "
                "FROM employees e JOIN departments d ON d.id = e.department_id) WHERE rnk <= 2"]),
    Spec("sql-oylik-tushum", "Oyma-oy tushum",
         "Har bir oy uchun do‘kon tushumini (`quantity * price` yig‘indisi) va yil boshidan shu oygacha "
         "jamlangan tushumni chiqaring. Faqat buyurtma bo‘lgan oylar, oy bo‘yicha o‘sish tartibida.\n\n"
         "Maslahat: oyni `strftime('%Y-%m', order_date)` bilan oling; jamlangan yig‘indi — "
         "`SUM(...) OVER (ORDER BY ...)`.",
         "Uch ustun: `month` (masalan `2025-03`), `revenue`, `running_total`. Tartib muhim.", "shop",
         ["products", "orders", "order_items"],
         "SELECT month, revenue, SUM(revenue) OVER (ORDER BY month) AS running_total FROM ("
         "SELECT strftime('%Y-%m', o.order_date) AS month, SUM(oi.quantity * p.price) AS revenue FROM orders o "
         "JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id GROUP BY month) "
         "ORDER BY month", D.HARD, ["window-functions", "date-functions"],
         wrong=["SELECT strftime('%Y-%m', o.order_date) AS month, SUM(oi.quantity * p.price) AS revenue, "
                "SUM(oi.quantity * p.price) FROM orders o JOIN order_items oi ON oi.order_id = o.id "
                "JOIN products p ON p.id = oi.product_id GROUP BY month ORDER BY month"],
         ordered=True),
    Spec("sql-ketma-ket-uch-kun", "Uch kun ketma-ket",
         "Kamida **uch kun ketma-ket** (masalan, 5, 6 va 7-mart) har kuni buyurtma bergan mijozlarning "
         "ismlarini chiqaring, har birini bir marta. Bir kunda bir nechta buyurtma bo‘lishi mumkin.\n\n"
         "Maslahat: `date(order_date, '+1 day')` sanaga bir kun qo‘shadi.",
         "Bitta ustun: `name`.", "shop", ["customers", "orders"],
         "SELECT DISTINCT c.name FROM customers c JOIN orders a ON a.customer_id = c.id "
         "JOIN orders b ON b.customer_id = c.id AND b.order_date = date(a.order_date, '+1 day') "
         "JOIN orders d ON d.customer_id = c.id AND d.order_date = date(a.order_date, '+2 day')",
         D.HARD, ["join", "date-functions"],
         wrong=["SELECT DISTINCT c.name FROM customers c JOIN orders a ON a.customer_id = c.id "
                "JOIN orders b ON b.customer_id = c.id AND b.order_date = date(a.order_date, '+1 day')",
                "SELECT c.name FROM customers c JOIN orders o ON o.customer_id = c.id "
                "GROUP BY c.id HAVING COUNT(DISTINCT o.order_date) >= 3"]),
]


def build(spec: Spec) -> dict:
    """The problem's data sets and their expected results; CommandError when the hidden data
    can't tell the reference query from one of its near misses."""
    theme = THEMES[spec.theme]
    schema, seed = dump(theme(random.Random(f"{spec.slug}/sample"), big=False), spec.tables)
    _, check_seed = dump(theme(random.Random(f"{spec.slug}/check"), big=True), spec.tables)
    results = {}
    for name, data in (("sample", seed), ("check", check_seed)):
        status, _, rows = sql_judge.run_query_table(schema, data, spec.solution, 1000)
        if status != "OK" or not rows:
            raise CommandError(f"{spec.slug}: the reference query gives {status}, {len(rows)} rows on {name} data")
        results[name] = sql_judge.format_rows(rows)
    if results["sample"] == results["check"]:
        raise CommandError(f"{spec.slug}: sample and check data give the same answer")
    for query in spec.wrong:
        status, rows = sql_judge.run_query(schema, check_seed, query, 1000)
        if status == "OK" and sql_judge.rows_match(rows, results["check"], ordered=spec.ordered):
            raise CommandError(f"{spec.slug}: the check data accepts a wrong query: {query}")
    return {"schema_sql": schema, "seed_sql": seed, "expected_result": results["sample"],
            "check_seed_sql": check_seed, "check_expected_result": results["check"], "ordered": spec.ordered}


class Command(BaseCommand):
    help = "Create/refresh the SQL problems (matched by slug), their data and expected results."

    def add_arguments(self, parser):
        parser.add_argument("--author", default=None, help="Username of the author (default: first staff user).")

    def handle(self, *args, **opts):
        author = (User.objects.get(username=opts["author"]) if opts["author"]
                  else User.objects.filter(is_staff=True).order_by("pk").first())
        if author is None:
            self.stderr.write("No staff user found; run `seed` first or pass --author.")
            return
        datasets = {spec.slug: build(spec) for spec in SPECS}  # all checked before anything is written
        with transaction.atomic():
            for spec in SPECS:
                problem, created = Problem.objects.update_or_create(slug=spec.slug, defaults=dict(
                    title=spec.title, statement_md=spec.statement, input_md="", output_md=spec.output,
                    difficulty=spec.difficulty, kind=Problem.Kind.SQL, author=author, tl_ms=1000,
                    is_public=True, status=Problem.Status.APPROVED,
                ))
                problem.tags.set([Tag.objects.update_or_create(name=t, defaults={"kind": Tag.Kind.SQL})[0]
                                  for t in spec.tags])
                SQLDataset.objects.update_or_create(problem=problem, defaults=datasets[spec.slug])
                self.stdout.write(f"{'created' if created else 'updated'} {spec.slug}")
        self.stdout.write(self.style.SUCCESS(f"{len(SPECS)} SQL problems"))
