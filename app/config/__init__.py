import os
from dynaconf import Dynaconf

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

settings = Dynaconf(
    settings_files=[os.path.join(_project_root, "settings.toml")],
    environments=False,
    load_dotenv=True,
)

settings.BASE_DIR = _project_root
