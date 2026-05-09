from pathlib import Path
import os


def load_env_file(env_path: str = ".env") -> bool:
    path = Path(env_path)
    if not path.exists():
        return False

    loaded_any = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ[key] = value
        loaded_any = True

    return loaded_any
