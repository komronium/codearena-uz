import os
import tempfile

import pytest

from judge.sandbox import SOURCE_FILENAME, compile, run_test

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
    # 0o777: compiled languages write their output (main / Main.class) into
    # this dir as container-user `nobody`, who needs write, not just read+exec.
    d = tempfile.mkdtemp(dir=os.environ.get("JUDGE_WORK_DIR"))
    os.chmod(d, 0o777)
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
    out, verdict, ms = run_test(lang, d, "1 2\n", 1000, 128)
    assert verdict == "OK" and out.strip() == "3"
