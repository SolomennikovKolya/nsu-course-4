
Структура UDDM:
```
root
 └── block*

block = (text|list|table)

text
 └── p+
list
 └── item+
      └── block+ 
table
 └── row+
      └── cell+
           └── block+
```

Пример файла в формате UDDM:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
    <text>
        <p>Министерство науки и высшего образования Российской Федерации</p>
        <p>Новосибирский национальный исследовательский государственный университет</p>
        <p>Факультет информационных технологий</p>
        <p>Кафедра общей информатики</p>
    </text>
    <text>
        <p>ЗАЯВЛЕНИЕ</p>
        <p>о направлении на практику</p>
    </text>
    <text>
        <p>От обучающегося Соломенникова Николая Александровича (Ф.И.О.)</p>
        <p>4 курса, группы № 22204</p>
        <p>направление 09.03.01 (код и наименование направления)</p>
        <p>Информатика и вычислительная техника</p>
        <p>направленность (профиль) Программная инженерия и компьютерные науки (наименование профиля)</p>
    </text>
    <text>
        <p>Прошу направить меня на производственную практику</p>
        <p>(указывается наименование практики)</p>
        <p>в ФГБУН Институт математики им. С. Л. Соболева СО РАН</p>
        <p>630090, г. Новосибирск, пр. Академика Коптюга, 4</p>
    </text>
    <table>
        <row>
            <cell><text><p>Дата начала практики</p></text></cell>
            <cell><text><p>29.09.2025</p></text></cell>
        </row>
        <row>
            <cell><text><p>Дата окончания практики</p></text></cell>
            <cell><text><p>23.12.2025</p></text></cell>
        </row>
    </table>
    <text>
        <p>Дата: «20» сентября 2025 г.</p>
    </text>
    <text>
        <p>Руководитель ВКР Пальчунов Дмитрий Евгеньевич, зав. кафедрой</p>
        <p>(Ф.И.О. полностью) (должность)</p>
    </text>
</root>
```

Контекст документа:
```python
class DocumentContext:
    def __init__(self, doc: Document):
        self.document: Document = doc
        self._uddm: Optional[UDDM] = None
        self._extr_res: Optional[ExtractionResult] = None
        self._draft_graph: Optional[DraftGraph] = None
        self._template_ctx: Optional[TemplateContext] = None

    @property
    def uddm(self) -> Optional[UDDM]:
        if self._uddm is not None:
            return self._uddm
        try:
            self._uddm = UDDM.load(self.document.uddm_file_path())
            return self._uddm
        except Exception:
            return None

    @uddm.setter
    def uddm(self, uddm: Optional[UDDM]):
        self._uddm = uddm

    # ... аналогичные пары свойств для других тяжёлых полей ...

    def unload(self):
        self._uddm = None
        self._extr_res = None
        self._draft_graph = None
        if self._template_ctx:
            self._template_ctx.unload()
            self._template_ctx = None

@contextmanager
def document_context(doc: Document):
    ctx = DocumentContext(doc)
    try:
        yield ctx
    finally:
        ctx.unload()
```

Пример политик слияния:
```ttl
:обучаетсяВГруппе a owl:ObjectProperty ;
    rdfs:domain :Студент ;
    rdfs:range :Группа ;
    :mergePolicy :Policy_SetByDate .

:телефон a owl:DatatypeProperty ;
    rdfs:domain :Персона ;
    rdfs:range xsd:string ;
    :mergePolicy :Policy_Add .

:авторВКР a owl:ObjectProperty ;
    rdfs:domain :ВКР ;
    rdfs:range :Студент ;
    :mergePolicy :Policy_Set .
```

Rollback документа:
```python
def rollback_document(self, document_id: str) -> bool:
    history = self.load_history_entries()
    new_history = [e for e in history if e.document_id != document_id]
    if len(new_history) == len(history):
        return False
    self.save_history_entries(new_history)
    self.rebuild_journal()
    full = self.assemble_full_graph(new_history)
    self.write_combined_ontology(full.graph)
    return True
```

Пример кода шаблона:
```python
from core import *

class TemplateCode(BaseTemplateCode):

    def classify(self, doc_name: str, uddm: UDDM) -> bool:
        name = (doc_name or "").lower()
        if all(w in name for w in ["заявление", "практику", "пиикн"]):
            return True
        full_text = str(uddm.root).lower()
        return all(w in full_text for w in [
            "заявление", "прошу направить меня", "практику",
        ])

    def fields(self) -> list[Field]:
        return [
            Field(
                "student_name", "ФИО обучающегося",
                sel().find(ElementType.P, Predicate.contains_text("(Ф.И.О.)")),
                ext().before("(Ф.И.О.)").keep_letters_and_spaces().normalize_spaces(),
                norm().concept(PersonConcept),
            ),
            Field(
                "group_number", "Номер учебной группы",
                sel().find(ElementType.P, Predicate.contains_text("Группа")).first(),
                ext().regex(r"Группа\s+([0-9A-Za-zА-Яа-я\-]+)", group=1),
                norm().concept(GroupConcept),
            ),
            # << другие поля... >>
        ]

    def build(self, b: TemplateGraphBuilder):
        student = b.individual("student_name", PersonConcept, role=ONTO.Студент)
        b.add_object_property(student, ONTO.обучаетсяВГруппе,
            b.individual("group_number", GroupConcept))
        b.add_object_property(student, ONTO.обучаетсяНаНаправлении,
            b.direction("direction_code", name_field="direction_name"))
        b.add_object_property(student, ONTO.имеетПрофиль,
            b.individual("profile_name", ProfileConcept))
        # << другие факты... >>
```

Концепты и идентификация индивидов:
```
PersonConcept("Соломенникову Николаю Александровичу")
                        ↓
        Соломенников Николай Александрович
                        ↓
            ключ = «соломенников|н|а»
                        ↓
            IRI = Персона_<sha1(ключ)>
```