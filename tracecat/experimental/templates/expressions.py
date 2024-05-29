"""A module for templated expressions.


Motivation
----------
- Formalize the templated expression syntax and vocabulary.
- By doing so, in TypeScript we can infer the final type of the expression to improve type checking and validation.
    - This helps with type checking in the UI at form submission time

Template
--------
A string with one or more templated expressions, e.g. "${{ $.webhook.result -> int }}"

Expression
----------
The constituients of the template, "${{ <expression> -> <type> }}" "$.webhook.result -> int"
The expression and type together are referred to as typed/annotated expression


Resolved Type
-------------
The type to cast the result to, e.g. "int" or "str" or "float"

Context
-------
The root level namespace of the expression, e.g. "SECRETS" or "$" or "FNS".
Anything that isn't a global context like SECRETS/FNS is assumed to be a jsonpath, e.g. "$.webhook.result"

Operand
-------
The data structure to evaluate the expression on, e.g. {"webhook": {"result": 42}}

Usage
-----
For secrets, you should:
1. Extract the secrets from the templated object
2. Fetch the secrets
3. Populate the templated object with the actual values

"""

from typing import Any, Literal, TypeVar

import jsonpath_ng
from jsonpath_ng.exceptions import JsonPathParserError

from tracecat.experimental.templates import patterns

T = TypeVar("T")
token_pattern = r""
_BUILTIN_TYPE_NAP = {
    "int": int,
    "float": float,
    "str": str,
    # TODO: Perhaps support for URLs for files?
}
TemplateStr = str
"""An annotated template string that can be resolved into a type T."""

OperandType = dict[str, Any]


class TemplateExpression:
    """A expression that resolves into a type T."""

    _context: Literal["SECRETS", "FNS", "ACTIONS", "INPUTS"]
    """The context of the expression, e.g. SECRETS, FNS, ACTIONS, INPUTS, or a jsonpath."""

    _expr: str
    """The expression to evaluate, e.g. webhook.result."""

    _operand: OperandType | None

    def __init__(
        self, template: TemplateStr, *, operand: OperandType | None = None
    ) -> None:
        self._template = template
        match = patterns.TYPED_TEMPLATE.match(template)
        if not match:
            raise ValueError(f"Invalid template: {template!r}")

        # Top level types
        self._context = match.group("context")
        self._expr = match.group("expr")
        self._resolve_typename = match.group("type")
        # If no type is specified, do not cast the result
        self._resolve_type = _BUILTIN_TYPE_NAP.get(self._resolve_typename)

        # Operand
        self._operand = operand

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return (
            "Templatedexpression("
            f"template={self._template},"
            f" expression={self._expr},"
            f" typename={self._resolve_typename},"
            f" type={self._resolve_type}),"
            f" operand={self._operand})"
        )

    def _resolve_fn(self) -> Any:
        return NotImplemented
        # matched_fn = patterns.EXPR_INLINE_FN.match(self._expr)
        # if not matched_fn:
        #     raise ValueError(f"Invalid function expression: {self._expr!r}")
        # print("Got an inline function")
        # fn_name = matched_fn.group("func")
        # fn_args = re.split(r",\s*", matched_fn.group("args"))
        # # Get the function, likely from some regsitry or module and call it
        # print(fn_name, fn_args)
        # return fn_name

    def result(self) -> Any:
        """Evaluate the templated expression and return the result."""
        match self._context:
            case "FNS":
                ret = self._resolve_fn()
            case _:
                if not self._operand:
                    raise ValueError("Operand is required for templated jsonpath.")
                ret = eval_jsonpath(self._expr, self._operand[self._context])

        if not self._resolve_type:
            return ret
        try:
            # Attempt to cast the result into the desired type
            return self._resolve_type(ret)
        except Exception as e:
            raise ValueError(f"Could not cast {ret!r} to {self._resolve_type!r}") from e


def eval_jsonpath(expr: str, operand: dict[str, Any]) -> Any:
    if operand is None or not isinstance(operand, dict):
        raise ValueError("A dict-type operand is required for templated jsonpath.")
    try:
        # Try to evaluate the expression
        jsonpath_expr = jsonpath_ng.parse(expr)
    except JsonPathParserError as e:
        raise ValueError(f"Invalid jsonpath {expr!r}") from e
    matches = [found.value for found in jsonpath_expr.find(operand)]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        return matches
    else:
        # We know that if this function is called, there was a templated field.
        # Therefore, it means the jsonpath was valid but there was no match.
        raise ValueError(f"Operand has no path {expr!r}. Operand: {operand}.")