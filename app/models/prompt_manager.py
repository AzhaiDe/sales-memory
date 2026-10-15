import os
from app.config.logger_setup import logger
from jinja2 import DebugUndefined, Template


def _render_str(content: str, synopsis: dict[str, str]) -> str:
    tm = Template(content, undefined=DebugUndefined)
    return tm.render(synopsis)


def _render_file(file: str, synopsis: dict[str, str]) -> str:
    res = ""
    try:
        with open(file, "r", encoding="utf-8") as fp:
            res = _render_str(fp.read(), synopsis)
        if len(res) == 0:
            logger.error("Empty Prompt Format, Please check {}".format(file))
    except Exception as e:
        logger.error(f"Prompt Render Error: {e}")
    return res


class PromptManager:
    def __init__(self, tenant_id: str):
        self._prompt_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", tenant_id)
        self._prompt: str = ""

    def load_prompt(self, prompt_name, synopsis: dict[str, str] = dict()) -> str:
        custom_file: str = os.path.join(self._prompt_path, "{}.txt".format(prompt_name))
        if os.path.isfile(custom_file):
            file: str = custom_file
        else:
            file: str = os.path.join(self._prompt_path, "{}.txt".format(prompt_name))
        self._prompt = _render_file(file, synopsis)
        return self._prompt
