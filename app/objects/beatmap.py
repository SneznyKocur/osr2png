from pathlib import Path

import requests
from rosu_pp_py import Beatmap as PPBeatmap
from rosu_pp_py import Performance, PerformanceAttributes
from ossapi.models import Beatmap as osu_beatmap
import app.utils
from app.utils import api
#
CACHE_FOLDER: Path = app.utils.CACHE_FOLDER / "osu"
SOMETHING_FUCKED_UP: str = "SOMETHING FUCKED UP"

#
CACHE_FOLDER.mkdir(exist_ok=True, parents=True)

# URL(s)
OSU_RAW_URL: str = "https://osu.ppy.sh/osu/{id}"
OSU_BACKGROUND_URL: str = "https://assets.ppy.sh/beatmaps/{set_id}/covers/fullsize.jpg"
KITSU_MD5_URL: str = "https://osu.direct/api/md5/{md5}"

# Internal
USER_AGENT: str = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
)


class Beatmap:
    data: dict[str, dict[str, str]]

    def __init__(
        self, data: dict[str, dict[str, str]] = {}, beatmap_path: Path | None = None
    ) -> None:
        self.data: dict[str, dict[str, str]] = data
        self.http: requests.Session = requests.Session()
        self.path = beatmap_path

        # Set header
        self.http.headers.update({"User-Agent": USER_AGENT})


    """ trollhd """

    @property
    def id(self) -> int:
        return int(self.data.get("Metadata", {}).get("BeatmapID", 0))

    @property
    def set_id(self) -> int:
        return int(self.data.get("Metadata", {}).get("BeatmapSetID", 0))

    @property
    def artist(self) -> str:
        return self.data.get("Metadata", {}).get("Artist", SOMETHING_FUCKED_UP)

    @property
    def title(self) -> str:
        return self.data.get("Metadata", {}).get("Title", SOMETHING_FUCKED_UP)

    @property
    def difficulty(self) -> str:
        return self.data.get("Metadata", {}).get("Version", SOMETHING_FUCKED_UP)

    @property
    def max_combo(self) -> int:
        return int(self.data.get("Metadata", {}).get("MaxCombo", 0))

    """ calcs """

    def calculate_pp(
        self, mods: int, acc: float, combo: int, misses: int
    ) -> PerformanceAttributes:
        if self.path and not self.path.exists():
            print(
                "[Beatmap] The fuck, cached beatmap file is gone... Try running the thing again?"
            )

        pp_bmap = PPBeatmap(path=str(self.path))
        pp_calc = Performance(mods=mods)

        # params
        pp_calc.set_accuracy(acc)
        pp_calc.set_combo(combo)
        pp_calc.set_misses(misses)

        return pp_calc.calculate(pp_bmap)

    """ files """

    def get_beatmap_background(self) -> Path:
        # Download background if doesnt exists
        if not (background_file := CACHE_FOLDER / f"{self.set_id}_bg.png").exists():
            print("[API] Getting beatmap background from osu! /assets/,", end="")
            with self.http.get(OSU_BACKGROUND_URL.format(set_id=self.set_id)) as res:
                if res.status_code != 200:
                    print(" failed.")
                    print(
                        "[API] Failed to get beatmap background, using the default one."
                    )
                    return app.utils.CACHE_FOLDER / "default_background.png"

                print(" success!")
                background_file.write_bytes(res.content)

        return background_file

    """ factories """
    @classmethod
    def from_md5(cls, md5: str) -> osu_beatmap:
        Api = api().api
        beatmap = Api.beatmap(checksum=md5)
        bmap = cls.from_id(beatmap.id)
        # HACK: lol
        bmap.data["Metadata"]["MaxCombo"] = beatmap.max_combo  # type: ignore
        return bmap

    @classmethod
    def from_id(cls, id: int):
        # Get raw .osu file from osu, if not in cache
        if not (beatmap_file := CACHE_FOLDER / str(id)).exists():
            print("[API] Getting beatmap from osu! /osu/,", end="")

            with beatmap.http.get(OSU_RAW_URL.format(id=id)) as res:
                if res.status_code != 200:
                    print(" failed.")
                    print("[API] Failed to get beatmap file from osu!.")
                    print(
                        "[API] If this is a custom beatmap, please pass the beatmap path with `-b` param."
                    )
                    exit(1)

                print(" success!")
                beatmap_file.write_bytes(res.content)
                cls.path = beatmap_file
        cls.path =  CACHE_FOLDER / str(id)
        return cls.from_osu_file(cls.path)
    @classmethod
    def from_osu_file(cls, path: Path) -> "Beatmap":
        beatmap: "Beatmap" = cls(beatmap_path=path)

        beatmap.data |= beatmap._parse_beatmap_file_from_path(path)
        return beatmap

    """ spooky shit """

    @staticmethod
    def _parse_beatmap_file_from_path(path: Path) -> dict[str, dict[str, str]]:
        """really quick and dirty beatmap parser"""

        data: dict[str, dict[str, str]] = {}
        category: str = ""

        # NOTE: in linux this works just fine
        #       but on windows thing just shits the bed, fuck you windows.
        for line in (
            path.read_bytes().decode(encoding="utf-8", errors="ignore").splitlines()
        ):
            if not line.strip():
                continue

            if line.startswith("["):
                category = line.replace("[", "").replace("]", "")
                data[category] = {}
                continue

            match category:
                case "General" | "Editor" | "Metadata" | "Difficulty":
                    items = line.split(":")
                    data[category][items[0]] = items[1]
        return data


if __name__ == "__main__":
    b = Beatmap.from_id(2690223)
    print(b.title)
    print(b.difficulty)
    print(b.calculate_pp(mods=16, acc=100.0, combo=532, misses=0))
