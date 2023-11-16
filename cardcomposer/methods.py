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
    def ensure_ints(numbers: tuple[Union[float, int], ...]) -> tuple[int, ...]:
        """
        Used to ensure a number sequence contains only integers, in cases where:
        - Integer values are a requirement
        - Losing float precision is acceptable

        If the provided data is not a tuple or list of numbers, will raise an exception
        """

        if type(numbers) not in (tuple, list):
            raise TypeError(f"unable to process value (is not tuple or list): {numbers}")

        for number in numbers:
            if type(number) not in (float, int):
                raise TypeError(f"unable to process value (is not float or int): {number}")

        return tuple(round(number) for number in numbers)
