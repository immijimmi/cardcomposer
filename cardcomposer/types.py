from typing import Optional, Literal, Union, Any

type Deferred = dict[Union[Literal["deferred"], str], Any]
type Step = dict[str, Any]
type CardFaceLabel = Optional[str]
type ArithmeticOperator = Literal["+", "-", "*", "/", "//", "**", "%"]
