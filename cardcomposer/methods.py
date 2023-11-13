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
    def round_all(numbers):
        """
        Attempts to round all numbers in the provided sequence to int values, returning them as a new sequence.
        Fails quietly - if unable to round a value, it is returned as-is within its place in the sequence
        """

        result = []
        try:
            for num in numbers:
                try:
                    result.append(round(num))
                except TypeError:
                    result.append(num)

            return result
        except TypeError:
            return numbers
