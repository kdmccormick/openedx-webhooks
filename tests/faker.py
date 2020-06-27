import dataclasses
import functools
import inspect
import re
from typing import Dict, List, Tuple

class FakerException(Exception):
    status_code: int = 500

    def as_json(self):
        return {"error": str(self)}


class FakerModel:
    def as_json(self):
        return dataclasses.asdict(self)


def callback(path_regex, http_method="GET", data_type="json"):
    """Associate this method with a particular HTTP route."""
    def _decorator(func):
        func.callback_spec = (path_regex, http_method.upper(), data_type)
        @functools.wraps(func)
        def _decorated(self, request, context) -> Dict:
            match = re.match(path_regex, request.path)
            try:
                return func(self, match, request, context)
            except FakerException as ex:
                context.status_code = ex.status_code
                return ex.as_json()
        return _decorated
    return _decorator


class Faker:
    def __init__(self, host):
        self.host = host
        self.requests_mocker = None

    def install_mocks(self, requests_mocker) -> None:
        self.requests_mocker = requests_mocker
        for _, method in inspect.getmembers(self, inspect.ismethod):
            if hasattr(method, "callback_spec"):
                path_regex, http_method, data_type = method.callback_spec
                self.requests_mocker.register_uri(
                    http_method,
                    re.compile(fr"^{self.host}{path_regex}$"),
                    **{data_type: method},
                )

    def requests_made(self, path_regex: str = None, method: str = None) -> List[Tuple[str, str]]:
        """
        Returns a list of (method, url) pairs that have been made.

        If no method is provided, all methods are returned.
        """
        reqs = []
        for req in self.requests_mocker.request_history:
            if method is not None and method != req.method:
                continue
            if path_regex is not None and not re.search(path_regex, req.path):
                continue
            reqs.append((req.path, req.method))
        return reqs
