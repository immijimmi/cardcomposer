from json import loads
from typing import Optional

from .cardface import CardFace


class App:
    def __init__(self):
        with open("cards.json", "r") as data_file:
            cards_data: list[dict[str]] = loads(data_file.read())

        cardfaces = []
        template_lookup: dict[str, list[CardFace]] = {}
        while cards_data:
            cards_data_working = [*cards_data]
            cards_data.clear()

            processed_this_loop: int = 0
            while cards_data_working:
                single_card_data = cards_data_working.pop(0)

                label: Optional[str] = single_card_data.get("label")
                size: Optional[tuple[int, int]] = single_card_data.get("size")
                steps: tuple[dict[str], ...] = single_card_data.get("steps", ())
                is_template: bool = single_card_data.get("is_template", False)

                templates_labels: Optional[tuple[str]] = single_card_data.get("templates", ())

                templates = []
                for template_label in templates_labels:
                    matching_templates = template_lookup.get(template_label, [])

                    if len(matching_templates) == 0:  # No matching template found for this label
                        cards_data.append(single_card_data)  # Defer processing incase template has not yet been made
                        break
                    elif len(matching_templates) > 1:
                        raise RuntimeError(
                            f"unable to resolve {CardFace.__name__} template"
                            f" - multiple matching templates found under label: {template_label}"
                        )
                    else:
                        templates.append(matching_templates[0])

                if len(templates) == len(templates_labels):  # All templates resolved
                    cardface = CardFace(
                        label=label, size=size,
                        steps=steps, templates=templates,
                        is_template=is_template
                    )

                    processed_this_loop += 1
                    cardfaces.append(cardface)
                    if cardface.is_template and (cardface.label is not None):
                        template_lookup.setdefault(cardface.label, []).append(cardface)

            if processed_this_loop == 0:  # Presumably all deferred due to missing templates
                raise RuntimeError(
                    f"unable process the following {CardFace.__name__} data"
                    f" (unable to locate the required templates): {cards_data}"
                )

        for cardface in cardfaces:
            if not cardface.is_template:
                cardface.generate()
