# tools/

Script **deterministici e atomici** (livello **T** della triade A.N.T.).
Ogni tool: fa **UNA** cosa, input tipizzato → output tipizzato, testabile in
isolamento, nessun side effect nascosto, nessuna business logic ambigua.

> Navigation **ragiona**, Tools **eseguono**. Ogni tool ha il suo test.

Esempio: `<verbo>_<oggetto>.py` + `test_<verbo>_<oggetto>.py`
