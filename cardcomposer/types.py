from typing import Optional, Literal

type Deferred = dict[str]
type Step = dict[str]
type CardFaceLabel = Optional[str]
type ArithmeticOperator = Literal["+", "-", "*", "/", "//", "**", "%"]
