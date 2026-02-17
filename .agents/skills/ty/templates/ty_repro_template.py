from __future__ import annotations

from typing import TYPE_CHECKING


def build_params() -> object:
    """
    Replace `object` with the actual target type (TypedDict / TypeAlias), then:

    1) Type intermediate values first:
       item: SomeTypedDict = {...}
       items: SomeListAlias = [item]
       nested: SomeNestedTypedDict = {...}

    2) Type the final dict literal:
       params: SomeParamsTypedDict = {...}
       return params
    """
    raise NotImplementedError


if TYPE_CHECKING:
    # Put optional "bad examples" here, but keep them commented out so the file
    # still passes type checks by default.
    #
    # Example pattern (commented):
    #
    # bad: SomeTypedDict = {"mode": "typo"}  # should fail once uncommented
    #
    pass
