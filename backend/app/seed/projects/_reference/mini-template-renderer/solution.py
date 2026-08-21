import re


class TemplateError(Exception):
    """Raised when a template references a name not in the context."""


VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")
FOR = re.compile(
    r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}", re.DOTALL
)


def _substitute(text: str, context: dict) -> str:
    def replace(match):
        name = match.group(1)
        if name not in context:
            raise TemplateError(f"undefined variable: {name!r}")
        return str(context[name])

    return VAR.sub(replace, text)


def render(template: str, context: dict) -> str:
    """Render `{{ name }}` substitutions and `{% for x in xs %}` loops."""

    def replace_loop(match):
        loopvar, listvar, body = match.group(1), match.group(2), match.group(3)
        if listvar not in context:
            raise TemplateError(f"undefined variable: {listvar!r}")
        return "".join(
            _substitute(body, {**context, loopvar: item})
            for item in context[listvar]
        )

    without_loops = FOR.sub(replace_loop, template)
    return _substitute(without_loops, context)
