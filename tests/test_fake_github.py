import pytest
import requests
from glom import glom

from .fake_github import DoesNotExist as fake_github_DoesNotExist


class TestFaker:
    def test_requests_made(self, fake_github):
        requests.get("https://api.github.com/repos/xyzzy/quux/pulls/1")
        requests.get("https://api.github.com/repos/xyzzy/quux/pulls/1234")
        requests.post("https://api.github.com/repos/xyzzy/quux/labels")
        requests.delete("https://api.github.com/repos/xyzzy/quux/labels/bug123")
        assert fake_github.requests_made() == [
            ("/repos/xyzzy/quux/pulls/1", "GET"),
            ("/repos/xyzzy/quux/pulls/1234", "GET"),
            ("/repos/xyzzy/quux/labels", "POST"),
            ("/repos/xyzzy/quux/labels/bug123", "DELETE"),
        ]
        assert fake_github.requests_made(method="GET") == [
            ("/repos/xyzzy/quux/pulls/1", "GET"),
            ("/repos/xyzzy/quux/pulls/1234", "GET"),
        ]
        assert fake_github.requests_made(r"123") == [
            ("/repos/xyzzy/quux/pulls/1234", "GET"),
            ("/repos/xyzzy/quux/labels/bug123", "DELETE"),
        ]
        assert fake_github.requests_made(r"123", "GET") == [
            ("/repos/xyzzy/quux/pulls/1234", "GET"),
        ]


class TestUsers:
    def test_get_me(self, fake_github):
        resp = requests.get("https://api.github.com/user")
        assert resp.status_code == 200
        assert resp.json() == {"login": "webhook-bot"}

    def test_get_user(self, fake_github):
        fake_github.make_user(login="nedbat", name="Ned Batchelder")
        resp = requests.get("https://api.github.com/users/nedbat")
        assert resp.status_code == 200
        uj = resp.json()
        assert uj["login"] == "nedbat"
        assert uj["name"] == "Ned Batchelder"
        assert uj["type"] == "User"
        assert uj["url"] == "https://api.github.com/users/nedbat"


class TestRepos:
    def test_make_repo(self, fake_github):
        repo = fake_github.make_repo("an-org", "a-repo")
        assert repo.owner == "an-org"
        assert repo.repo == "a-repo"
        repo2 = fake_github.get_repo("an-org", "a-repo")
        assert repo == repo2


class TestRepoLabels:
    def test_get_default_labels(self, fake_github):
        fake_github.make_repo("an-org", "a-repo")
        resp = requests.get(f"https://api.github.com/repos/an-org/a-repo/labels")
        assert resp.status_code == 200
        labels = resp.json()
        assert isinstance(labels, list)
        assert len(labels) == 9
        assert {"name": "invalid", "color": "e4e669", "description": "This doesn't seem right"} in labels

    def test_create_label(self, fake_github):
        repo = fake_github.make_repo("an-org", "a-repo")
        # At first, the label doesn't exist.
        with pytest.raises(fake_github_DoesNotExist):
            repo.get_label("nice")
        # We make a label with the API.
        resp = requests.post(
            "https://api.github.com/repos/an-org/a-repo/labels",
            json={"name": "nice", "color": "ff0000"},
        )
        assert resp.status_code == 201
        label_json = resp.json()
        assert label_json["name"] == "nice"
        assert label_json["color"] == "ff0000"
        assert label_json["description"] is None

        # Now the label does exist.
        label = repo.get_label("nice")
        assert label.name == "nice"
        assert label.color == "ff0000"
        assert label.description is None

    def test_cant_create_duplicate_label(self, fake_github):
        fake_github.make_repo("an-org", "a-repo")
        resp = requests.post(
            "https://api.github.com/repos/an-org/a-repo/labels",
            json={"name": "bug", "color": "ff0000"},
        )
        assert resp.status_code == 422
        error_json = resp.json()
        assert error_json["message"] == "Validation Failed"
        assert error_json["errors"] == [
            {"resource": "Label", "code": "already_exists", "field": "name"},
        ]

    BOGUS_COLORS = ["red please", "#ff000", "f00", "12345g"]

    @pytest.mark.parametrize("bogus_color", BOGUS_COLORS)
    def test_cant_create_bogus_color(self, fake_github, bogus_color):
        fake_github.make_repo("an-org", "a-repo")
        resp = requests.post(
            "https://api.github.com/repos/an-org/a-repo/labels",
            json={"name": "bug", "color": bogus_color},
        )
        assert resp.status_code == 422
        error_json = resp.json()
        assert error_json["message"] == "Validation Failed"
        assert error_json["errors"] == [
            {"resource": "Label", "code": "invalid", "field": "color"},
        ]

    def test_patch_label(self, fake_github):
        repo = fake_github.make_repo("an-org", "a-repo")
        resp = requests.patch(
            "https://api.github.com/repos/an-org/a-repo/labels/help%20wanted",
            json={"name": "help wanted", "color": "dedbee", "description": "Please?"},
        )
        assert resp.status_code == 200
        label_json = resp.json()
        assert label_json["name"] == "help wanted"
        assert label_json["color"] == "dedbee"
        assert label_json["description"] == "Please?"

        label = repo.get_label("help wanted")
        assert label.name == "help wanted"
        assert label.color == "dedbee"
        assert label.description == "Please?"

    def test_cant_patch_missing_label(self, fake_github):
        fake_github.make_repo("an-org", "a-repo")
        resp = requests.patch(
            "https://api.github.com/repos/an-org/a-repo/labels/xyzzy",
            json={"name": "xyzzy", "color": "dedbee", "description": "Go away"},
        )
        assert resp.status_code == 404
        assert resp.json()["message"] == "Label an-org/a-repo 'xyzzy' does not exist"

    @pytest.mark.parametrize("bogus_color", BOGUS_COLORS)
    def test_cant_patch_bogus_color(self, fake_github, bogus_color):
        fake_github.make_repo("an-org", "a-repo")
        resp = requests.patch(
            "https://api.github.com/repos/an-org/a-repo/labels/bug",
            json={"name": "bug", "color": bogus_color},
        )
        assert resp.status_code == 422
        error_json = resp.json()
        assert error_json["message"] == "Validation Failed"
        assert error_json["errors"] == [
            {"resource": "Label", "code": "invalid", "field": "color"},
        ]

    def test_delete_label(self, fake_github):
        repo = fake_github.make_repo("an-org", "a-repo")
        # At first, the label does exist.
        assert repo.get_label("help wanted").color == "008672"

        # Delete the label.
        resp = requests.delete("https://api.github.com/repos/an-org/a-repo/labels/help%20wanted")
        assert resp.status_code == 204

        # Now the label doesn't exist.
        with pytest.raises(fake_github_DoesNotExist):
            repo.get_label("help wanted")

    def test_cant_delete_missing_label(self, fake_github):
        fake_github.make_repo("an-org", "a-repo")
        # Delete the label.
        resp = requests.delete("https://api.github.com/repos/an-org/a-repo/labels/xyzzy")
        assert resp.status_code == 404


class TestPullRequests:
    def test_make_pull_request(self, fake_github):
        repo = fake_github.make_repo("an-org", "a-repo")
        pr = repo.make_pull_request(
            user="some-user",
            title="Here is a pull request",
            body="It's a good pull request, you should merge it.",
        )
        resp = requests.get(f"https://api.github.com/repos/an-org/a-repo/pulls/{pr.number}")
        assert resp.status_code == 200
        prj = resp.json()
        assert prj["number"] == pr.number
        assert prj["user"]["login"] == "some-user"
        assert prj["user"]["name"] == "Some User"
        assert prj["title"] == "Here is a pull request"
        assert prj["body"] == "It's a good pull request, you should merge it."
        assert prj["state"] == "open"
        assert prj["labels"] == []
        assert prj["base"]["repo"]["full_name"] == "an-org/a-repo"
        assert prj["html_url"] == f"https://github.com/an-org/a-repo/pull/{pr.number}"

    def test_no_such_pull_request(self, fake_github):
        fake_github.make_repo("an-org", "a-repo")
        resp = requests.get(f"https://api.github.com/repos/an-org/a-repo/pulls/99")
        assert resp.status_code == 404
        assert resp.json()["message"] == "Pull request an-org/a-repo #99 does not exist"

    def test_no_such_repo_for_pull_request(self, fake_github):
        fake_github.make_repo("an-org", "a-repo")
        resp = requests.get(f"https://api.github.com/repos/some-user/another-repo/pulls/1")
        assert resp.status_code == 404
        assert resp.json()["message"] == "Repo some-user/another-repo does not exist"


class TestPullRequestLabels:
    def test_updating_labels(self, fake_github):
        repo = fake_github.make_repo("an-org", "a-repo")
        pr = repo.make_pull_request(
            title="Here is a pull request",
            body="It's a good pull request, you should merge it.",
        )
        assert pr.labels == set()

        resp = requests.patch(
            f"https://api.github.com/repos/an-org/a-repo/issues/{pr.number}",
            json={"labels": ["new label", "bug", "another label"]},
        )
        assert resp.status_code == 200
        assert pr.labels == {"new label", "bug", "another label"}
        assert repo.get_label("new label").color == "ededed"
        assert repo.get_label("bug").color == "d73a4a"
        assert repo.get_label("another label").color == "ededed"

        resp = requests.get(
            f"https://api.github.com/repos/an-org/a-repo/pulls/{pr.number}"
        )
        assert resp.status_code == 200
        prj = resp.json()
        assert prj["title"] == "Here is a pull request"
        label_summary = [(l["name"], l["color"]) for l in prj["labels"]]
        assert label_summary == [
            ("another label", "ededed"),
            ("bug", "d73a4a"),
            ("new label", "ededed"),
        ]


class TestComments:
    def test_listing_comments(self, fake_github):
        repo = fake_github.make_repo("an-org", "a-repo")
        pr = repo.make_pull_request()
        assert pr.comments == []
        resp = requests.get(
            f"https://api.github.com/repos/an-org/a-repo/issues/{pr.number}/comments"
        )
        assert resp.status_code == 200
        assert resp.json() == []

        pr.add_comment(user="tusbar", body="This is my comment")
        pr.add_comment(user="feanil", body="I love this change!")
        resp = requests.get(
            f"https://api.github.com/repos/an-org/a-repo/issues/{pr.number}/comments"
        )
        assert resp.status_code == 200
        summary = glom(resp.json(), [{"u": "user.login", "b": "body"}])
        assert summary == [
            {"u": "tusbar", "b": "This is my comment"},
            {"u": "feanil", "b": "I love this change!"},
        ]

    def test_posting_comments(self, fake_github):
        repo = fake_github.make_repo("an-org", "a-repo")
        pr = repo.make_pull_request()

        resp = requests.post(
            f"https://api.github.com/repos/an-org/a-repo/issues/{pr.number}/comments",
            json={"body": "I'm making a comment"},
        )
        assert resp.status_code == 200

        assert pr.comments[0].user.login == "webhook-bot"
        assert pr.comments[0].body == "I'm making a comment"
