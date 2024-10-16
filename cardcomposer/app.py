from json import loads
from typing import Optional, Union
from sys import stderr, getsizeof
import os
import logging

from .cardface import CardFace
from .extensions import PresetSteps, PresetValues
from .methods import Methods
from .constants import Constants
from .types import Deferred, Step, CardFaceLabel


class App:
    def __init__(self):
        self.logger = logging.getLogger(CardFace.__name__)
        self.logger.addHandler(logging.StreamHandler(stderr))
        self.logger.setLevel(logging.INFO)

    def run(self, do_catch_fatal: bool = True) -> bool:
        try:
            # Load manifest of all files containing card data
            try:
                self.logger.debug(
                    f"Attempting to load cards data manifest from {Constants.CARDS_DATA_MANIFEST_FILE_PATH}..."
                )
                with open(Constants.CARDS_DATA_MANIFEST_FILE_PATH, "r") as manifest_file:
                    cards_data_paths: list[str] = loads(manifest_file.read())
                self.logger.info(f"Manifest successfully loaded.")
            except FileNotFoundError:
                self.logger.warning(
                    f"Unable to locate cards data manifest, defaulting to {Constants.DEFAULT_CARDS_DATA_FILE_PATH}"
                )
                cards_data_paths = [Constants.DEFAULT_CARDS_DATA_FILE_PATH]

            # Load config
            config: Optional[dict[str]]
            try:
                self.logger.debug(f"Attempting to load config from {Constants.CONFIG_FILE_PATH}...")
                with open(Constants.CONFIG_FILE_PATH, "r") as config_file:
                    config: dict[str] = loads(config_file.read())
                self.logger.info(f"Config successfully loaded.")
            except FileNotFoundError:
                self.logger.warning(f"Unable to locate config file, defaulting to empty config.")
                config = None

            cards_data_files_paths = []
            # Resolve any entries which reference a directory into a list of .json files it contains, recursively
            for cards_data_path in cards_data_paths:
                if os.path.isdir(cards_data_path):
                    all_dir_file_paths = Methods.get_all_files_paths(cards_data_path)

                    for file_path in all_dir_file_paths:
                        if (len(file_path) > 4) and (file_path[-5:].lower() == ".json"):
                            cards_data_files_paths.append(file_path)
                else:
                    cards_data_files_paths.append(cards_data_path)

            # Load cards data from each file
            cards_data: list[dict[str]] = []
            for file_path in cards_data_files_paths:
                with open(file_path, "r") as data_file:
                    file_cards_data: Union[dict[str], list[dict[str]]] = loads(data_file.read())

                if type(file_cards_data) is list:
                    cards_data += file_cards_data
                elif type(file_cards_data) is dict:
                    cards_data.append(file_cards_data)
                else:
                    raise TypeError(f"invalid card data: {file_cards_data}")
            self.logger.info(f"All card data successfully loaded. Total size: {getsizeof(cards_data)}B")

            cardfaces = []
            for cardface_data in cards_data:
                label: Union[Deferred, CardFaceLabel] = cardface_data.get("label")
                size: Union[Deferred, Optional[tuple[int, int]]] = cardface_data.get("size")
                templates_labels: Union[Deferred, tuple[CardFaceLabel, ...]] = cardface_data.get("templates", ())
                steps: tuple[Step, ...] = cardface_data.get("steps", ())
                is_template: Union[Deferred, bool] = cardface_data.get("is_template", True)
                do_skip_generation: Union[Deferred, bool] = cardface_data.get("do_skip_generation", False)

                cardface = CardFace.with_extensions(PresetSteps, PresetValues)(
                    label=label,
                    templates_labels=templates_labels,
                    steps=steps,
                    size=size,
                    is_template=is_template,
                    do_skip_generation=do_skip_generation,
                    config=config,
                    logger=self.logger
                )
                cardfaces.append(cardface)
            self.logger.info(f"{CardFace.__name__} objects initialised.")

            for cardface in cardfaces:
                cardface.generate()

        except:
            if do_catch_fatal:
                self.logger.critical(f"A fatal exception has occurred.", exc_info=True)
                return False
            else:
                raise

        finally:
            for handler in self.logger.handlers:
                handler.close()

        return True
