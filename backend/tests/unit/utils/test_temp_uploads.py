"""Temporary uploads belong to their uploader (#3185)."""

import pytest

from app.utils.temp_uploads import owns_temp_upload, temp_upload_folder


def test_folder_is_scoped_to_the_user():
    assert temp_upload_folder(7) == "tmp/7"


@pytest.mark.parametrize(
    "path",
    ["tmp/7/123/data.csv", "tmp/7/data.csv", "tmp/7/../7/data.csv"],
)
def test_user_owns_paths_in_their_folder(path):
    assert owns_temp_upload(path, 7)


@pytest.mark.parametrize(
    "path",
    [
        "tmp/8/123/data.csv",
        "tmp/7/../8/data.csv",  # traversal out of the user's own folder
        "tmp/70/data.csv",  # a prefix of the id is not the id
        "tmp/data.csv",
        "uploads/7/data.csv",
        "processing/7/data.csv",
        "tmp/7",
    ],
)
def test_user_does_not_own_other_paths(path):
    assert not owns_temp_upload(path, 7)
