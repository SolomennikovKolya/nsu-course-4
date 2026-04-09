def normalize(text: str) -> str:
    return (
        text.lower()
        .replace("ё", "е")
        .replace(" ", "_")
        .replace(".", "")
    )


class IRIBuilder:

    def student(self, full_name: str, group: str) -> str:
        ...

    def staff(self, full_name: str) -> str:
        ...

    def practice(self, student_uri: str, year: int) -> str:
        ...
