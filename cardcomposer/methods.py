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
    def ensure_ints(numbers: Union[tuple[Union[float, int], ...], Any]) -> Union[tuple[int, ...], Any]:
        """
        Used to ensure a number sequence contains only integers, in cases where:
        - Integer values are a requirement
        - Losing float precision is acceptable

        If the provided data is not a tuple or list of only numbers, it will be returned as-is
        """

        if type(numbers) not in (tuple, list):
            return numbers

        for number in numbers:
            if type(number) not in (float, int):
                return numbers

        return tuple(round(number) for number in numbers)

    @staticmethod
    def coalesce_list_to_tuple(value):
        if type(value) is list:
            return tuple(value)

        return value
