import os
import tempfile

import pytest

from judge.sandbox import SOURCE_FILENAME, compile, run_tests

pytestmark = pytest.mark.skipif(os.environ.get("JUDGE_TESTS") != "1", reason="needs docker; set JUDGE_TESTS=1")

A_PLUS_B_SOURCE = {
    "cpp": "#include <iostream>\nint main(){long long a,b;std::cin>>a>>b;std::cout<<a+b<<std::endl;}\n",
    "java": "import java.util.Scanner;\npublic class Main{public static void main(String[] a){"
            "Scanner s=new Scanner(System.in);long x=s.nextLong(),y=s.nextLong();System.out.println(x+y);}}\n",
    "node": "const l=require('fs').readFileSync(0,'utf8').trim().split(/\\s+/).map(Number);"
            "console.log(l[0]+l[1]);\n",
}


class Lang:
    def __init__(self, code, docker_image, compile_cmd, run_cmd, tl_multiplier):
        self.code, self.docker_image, self.compile_cmd, self.run_cmd, self.tl_multiplier = (
            code, docker_image, compile_cmd, run_cmd, tl_multiplier)


LANGS = {
    "cpp": Lang("cpp", "codearena-judge-cpp", "g++ -O2 -o main main.cpp", "./main", 1.0),
    "java": Lang("java", "codearena-judge-java", "javac Main.java", "java Main", 3.0),
    "node": Lang("node", "codearena-judge-node", "", "node main.js", 2.0),
}


def _src(lang_code: str, code: str) -> str:
    # Compiled langs need 0o777 (nobody writes build output); interpreted 0o755.
    d = tempfile.mkdtemp(dir=os.environ.get("JUDGE_WORK_DIR"))
    lang = LANGS[lang_code]
    os.chmod(d, 0o777 if lang.compile_cmd else 0o755)
    path = os.path.join(d, SOURCE_FILENAME[lang_code])
    with open(path, "w") as f:
        f.write(code)
    os.chmod(path, 0o644)
    return d


@pytest.mark.parametrize("lang_code", ["cpp", "java", "node"])
def test_a_plus_b_ac(lang_code):
    lang = LANGS[lang_code]
    d = _src(lang_code, A_PLUS_B_SOURCE[lang_code])
    ok, log = compile(lang, d)
    assert ok, log
    out, verdict, ms, kb = run_tests(lang, d, ["1 2\n"], 1000, 128)[0]
    assert verdict == "OK" and out.strip() == "3" and kb > 0


FLOOD_SOURCE = {
    "cpp": "#include <cstdio>\nint main(){static char b[65536]; for(auto&c:b)c='x';"
           " while(1) fwrite(b,1,sizeof b,stdout);}\n",
    "java": "public class Main{public static void main(String[] a){String s=\"x\".repeat(65536);"
            "while(true) System.out.print(s);}}\n",
    "node": "const s='x'.repeat(65536); while(true) process.stdout.write(s);\n",
}


@pytest.mark.parametrize("lang_code", ["cpp", "java", "node"])
def test_output_flood_is_ole(lang_code):
    # Only C++ dies of SIGXFSZ; Java and Node keep running with failed writes, so the
    # verdict has to come from the capped output size, not from how the program ended.
    lang = LANGS[lang_code]
    d = _src(lang_code, FLOOD_SOURCE[lang_code])
    ok, log = compile(lang, d)
    assert ok, log
    res = run_tests(lang, d, [""], 1000, 256, output_limit=1 << 20)
    assert [v for _, v, _, _ in res] == ["OLE"]
