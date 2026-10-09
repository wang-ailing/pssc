"""Preserve parsed constraint names through the AST-to-SV generation path."""
import re

import pytest
from pssparser.core import Factory

from pssc import Parser, generate_sv
from pssc.ast2ir import AstToIrTranslator


Factory.inst()


@pytest.mark.parametrize("owner", ["action", "struct"])
@pytest.mark.parametrize(
    "constraints, expected_names, expected_expressions",
    [
        (
            "constraint bounded { x >= 2; x <= 5; }",
            ["bounded"],
            ["(x >= 2)", "(x <= 5)"],
        ),
        (
            "constraint { x >= 2; x <= 5; }",
            ["_c_0"],
            ["(x >= 2)", "(x <= 5)"],
        ),
        (
            "constraint { x >= 2; } "
            "constraint ceiling { x <= 5; } "
            "constraint { x != 4; }",
            ["_c_0", "ceiling", "_c_2"],
            ["(x >= 2)", "(x <= 5)", "(x != 4)"],
        ),
    ],
    ids=["named", "anonymous", "mixed"],
)
def test_constraint_names_reach_generated_sv(
    tmp_path, owner, constraints, expected_names, expected_expressions
):
    if owner == "action":
        source = (
            "component pss_top { action Top { rand bit[4] x; "
            + constraints + " exec body {} } }"
        )
        type_name = "pss_top::Top"
    else:
        source = (
            "struct Packet { rand bit[4] x; " + constraints + " } "
            "component pss_top { action Top { exec body {} } }"
        )
        type_name = "Packet"

    parser = Parser()
    parser.parses([("constraint_names.pss", source)])
    ctx = AstToIrTranslator().translate(parser.link())
    assert not ctx.errors
    functions = [function for function in ctx.type_map[type_name].functions
                 if function.metadata.get("_is_constraint")]
    assert [function.name for function in functions] == expected_names
    assert all(isinstance(function.name, str) for function in functions)

    files = generate_sv(source, str(tmp_path), export_actions=["pss_top::Top"])
    generated = next(path for path in files if path.name == "zsp_gen_pkg.sv").read_text()
    assert re.findall(r"\bconstraint\s+(\w+)\s*\{", generated) == expected_names
    assert "ExprId object" not in generated
    for expression in expected_expressions:
        assert expression in generated
