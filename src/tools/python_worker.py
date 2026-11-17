"""Trusted harness. Run ONLY inside the isolated worker image, never on the host."""

import ast
import json
import os
import sys
import traceback
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

HARNESS_VERSION = "python_worker_v1"
SAFE_BUILTINS = {
    name: getattr(__builtins__, name)
    for name in (
        "abs",
        "all",
        "any",
        "enumerate",
        "len",
        "max",
        "min",
        "range",
        "sorted",
        "sum",
        "zip",
    )
}


def solve_request(request):
    code = request["code"]
    tree = ast.parse(code, filename="<generated>")
    allowed_numbers = {"0", "1", "2", "100"} | {c["value"] for c in request["constants"]}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef)):
            raise ValueError("imports, globals and classes are unavailable")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError("private names are unavailable")
        if isinstance(node, ast.Attribute) and node.attr not in {
            "sqrt",
            "ln",
            "exp",
            "copy_abs",
            "items",
            "keys",
            "values",
            "get",
            "append",
        }:
            raise ValueError("attribute unavailable: " + node.attr)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if str(node.value) not in allowed_numbers:
                raise ValueError("undeclared algorithm constant: " + str(node.value))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                numeric = Decimal(node.value)
            except Exception:
                continue
            if not numeric.is_finite() or node.value not in allowed_numbers:
                raise ValueError("undeclared numeric string")
    scope = {"__builtins__": SAFE_BUILTINS, "Decimal": Decimal}
    with localcontext() as context:
        context.prec, context.rounding = 34, ROUND_HALF_EVEN
        data = {k: Decimal(v["base_value"]) for k, v in request["operands"].items()}
        exec(compile(tree, "<generated>", "exec"), scope)
        result = scope["solve"](data)
        if not isinstance(result, dict) or set(result) != set(request["outputs"]):
            raise ValueError("output keys must match specification")
        output = {}
        for key, value in result.items():
            if type(value) not in (Decimal, int):
                raise ValueError("outputs must be Decimal or int")
            value = Decimal(value)
            if not value.is_finite():
                raise ValueError("non-finite output")
            output[key] = str(value)
        return output


def probe():
    with open("/proc/self/status") as stream:
        status = dict(line.strip().split(":", 1) for line in stream if ":" in line)

    def read(name):
        with open("/sys/fs/cgroup/" + name) as stream:
            return stream.read().strip()

    return dict(
        harness=HARNESS_VERSION,
        uid=os.getuid(),
        capabilities=status["CapEff"].strip(),
        seccomp=status["Seccomp"].strip(),
        interfaces=sorted(os.listdir("/sys/class/net")),
        memory=read("memory.max"),
        swap=read("memory.swap.max"),
        pids=read("pids.max"),
        cpu=read("cpu.max"),
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--probe"]:
        print(json.dumps(probe()))
    else:
        try:
            request = json.loads(sys.stdin.buffer.read(262145))
            print(json.dumps(dict(status="success", results=solve_request(request))))
        except BaseException as error:
            lines = traceback.format_exception(type(error), error, error.__traceback__)
            # Only container paths; no host environment or credentials enter the worker.
            print(json.dumps(dict(status="code_error", traceback="".join(lines)[-8192:])))
