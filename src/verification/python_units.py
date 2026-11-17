"""Conservative dimensional check for straight-line Decimal arithmetic, without exec.

Unknown Python constructs remain unverified. This check proves dimensions only;
financial definitions, operand roles and goal meaning still require M6 semantics.
"""

import ast
from fractions import Fraction


class UnitNotProven(ValueError):
    pass


def check_python_units(record):
    execution = record["executions"][-1]
    environment = {}

    def unit(name):
        return {} if name in {"ratio", "percent", "dimensionless"} else {name: Fraction(1)}

    def combine(left, right, sign=1):
        result = dict(left)
        for key, power in right.items():
            result[key] = result.get(key, Fraction(0)) + sign * power
        return {k: v for k, v in result.items() if v}

    def exponent(node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Decimal"
            and len(node.args) == 1
        ):
            return exponent(node.args[0])
        if isinstance(node, ast.Constant) and type(node.value) in {str, int, float}:
            return Fraction(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -exponent(node.operand)
        raise UnitNotProven("python_unit_exponent_unresolved")

    def dimensions(node):
        if isinstance(node, ast.Constant) and type(node.value) in {int, float, str}:
            exponent(node)  # Numeric constants only; handles are parsed below.
            return {}
        if isinstance(node, ast.Name) and node.id in environment:
            return environment[node.id]
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "data"
            and isinstance(node.slice, ast.Constant)
        ):
            return unit(record["operands"][node.slice.value]["unit"])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return dimensions(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = dimensions(node.left), dimensions(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if left != right:
                    raise ValueError("python_additive_unit_mismatch")
                return left
            if isinstance(node.op, (ast.Mult, ast.Div)):
                return combine(left, right, -1 if isinstance(node.op, ast.Div) else 1)
            if isinstance(node.op, ast.Pow) and not right:
                power = exponent(node.right)
                return {k: v * power for k, v in left.items() if v * power}
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in {"Decimal", "abs"}
                and len(node.args) == 1
                and not node.keywords
            ):
                return dimensions(node.args[0])
            if isinstance(node.func, ast.Attribute) and not node.args and not node.keywords:
                source = dimensions(node.func.value)
                if node.func.attr == "sqrt":
                    return {k: v / 2 for k, v in source.items()}
                if node.func.attr == "copy_abs":
                    return source
                if node.func.attr in {"ln", "exp"}:
                    if source:
                        raise ValueError("python_transcendental_unit_mismatch")
                    return {}
        raise UnitNotProven("python_unit_construct_unresolved")

    tree = ast.parse(execution["code"])
    if (
        len(tree.body) != 1
        or not isinstance(tree.body[0], ast.FunctionDef)
        or tree.body[0].name != "solve"
    ):
        raise UnitNotProven("python_unit_function_unresolved")
    for statement in tree.body[0].body:
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            environment[statement.targets[0].id] = dimensions(statement.value)
        elif isinstance(statement, ast.Return) and isinstance(statement.value, ast.Dict):
            outputs = {}
            for key, value in zip(statement.value.keys, statement.value.values, strict=True):
                if not isinstance(key, ast.Constant) or key.value not in execution["outputs"]:
                    raise UnitNotProven("python_unit_output_unresolved")
                actual = dimensions(value)
                if actual != unit(execution["outputs"][key.value]):
                    raise ValueError("python_output_unit_mismatch")
                outputs[key.value] = {k: str(v) for k, v in actual.items()}
            if set(outputs) != set(execution["outputs"]):
                raise UnitNotProven("python_unit_output_unresolved")
            return outputs
        else:
            raise UnitNotProven("python_unit_construct_unresolved")
    raise UnitNotProven("python_unit_return_unresolved")
