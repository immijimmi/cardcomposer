from typing import Optional, Literal, Union

type Deferred = dict[Union[Literal["deferred"], str]]
type Step = dict[str]
type CardFaceLabel = Optional[str]
type ArithmeticOperator = Literal["+", "-", "*", "/", "//", "**", "%"]
