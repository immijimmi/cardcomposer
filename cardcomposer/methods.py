from typing import Any, Union, Optional
from copy import deepcopy


class Methods:
    @staticmethod
    def try_copy(item: Any) -> Any:
        """
        A failsafe deepcopy wrapper
        """

        try:
            return deepcopy(item)
        except:
            return item

    @staticmethod
    def round_all(numbers: tuple[Union[int, float], ...], ignore_value: Any = None) -> Union[tuple[int, ...], Any]:
        if numbers == ignore_value:
            return ignore_value

        return tuple(round(num) for num in numbers)
