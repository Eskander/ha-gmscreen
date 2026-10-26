"""Load the vendored library without importing the Home Assistant integration.

``custom_components/gmscreen/__init__.py`` needs Home Assistant, but the ``api``
package inside it does not.  Loading it from its path as ``gmscreen_api`` keeps the
unit tests dependency free.
"""
import importlib.util
import pathlib
import sys

API_DIR = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "gmscreen" / "api"


def load():
    if "gmscreen_api" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "gmscreen_api", API_DIR / "__init__.py", submodule_search_locations=[str(API_DIR)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["gmscreen_api"] = module
        spec.loader.exec_module(module)
    return sys.modules["gmscreen_api"]


load()
