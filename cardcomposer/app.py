from json import loads
from typing import Optional
from sys import stderr
import logging

from .cardface import CardFace
from .extensions import PresetSteps, PresetValues
from .constants import Constants


class App:
    def __init__(self):
        self.logger = logging.getLogger(CardFace.__name__)
        self.logger.addHandler(logging.StreamHandler(stderr))
        self.logger.setLevel(logging.INFO)

        try:
            self.logger.debug(f"Attempting to load cards data manifest from {Constants.CARDS_DATA_MANIFEST_FILE_PATH}...")
            with open(Constants.CARDS_DATA_MANIFEST_FILE_PATH, "r") as manifest_file:
                cards_data_files_paths: list[str] = loads(manifest_file.read())

            self.logger.info(f"Manifest successfully loaded.")

        except FileNotFoundError:
            self.logger.warning(
                f"Unable to locate cards data manifest, defaulting to {Constants.DEFAULT_CARDS_DATA_FILE_PATH}"
            )
            cards_data_files_paths = [Constants.DEFAULT_CARDS_DATA_FILE_PATH]

        # Load cards data from each file
        cards_data: list[dict[str]] = []
        for file_path in cards_data_files_paths:
            with open(file_path, "r") as data_file:
                file_cards_data: list[dict[str]] = loads(data_file.read())
            cards_data += file_cards_data

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
                    cardface = CardFace.with_extensions(PresetSteps, PresetValues)(
                        label=label, size=size,
                        steps=steps, templates=templates,
                        is_template=is_template,
                        logger=self.logger
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
