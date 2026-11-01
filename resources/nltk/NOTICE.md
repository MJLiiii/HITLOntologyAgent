# Pinned English stopwords resource

Only `corpora/stopwords/english` and the original corpus `README` are included. They were copied unchanged from the prepared local NLTK archive and byte-checked against its ZIP entries on 1 November 2026.

- Official distribution: https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/stopwords.zip
- Archive SHA-256: `48c0e52d8b52546e827f53761fb30300c0ab94f70660d28bd65ba0a86270946b` (matches the [official index](https://github.com/nltk/nltk_data/blob/gh-pages/index.xml)).
- English SHA-256: `f6d005956f407dbc6ea32e5ff0c7e8e6f71488d3239b9023efdc7fc139d6375b`.
- Original README SHA-256: `e0365fde880eadb522f844cba2774529969b66b7406db7643cf260dcd77d6541`.

The original README identifies PostgreSQL/Snowball sources and the NLTK English-list augmentation. NLTK's [dataset license inventory](https://github.com/nltk/nltk_data/blob/gh-pages/DATASET-LICENSES.md) lists stopwords among data without a clarified license; its repository-wide Apache license does not establish a license for every corpus. Organizational redistribution/deployment review remains open. This local prototype records that uncertainty rather than labelling this dataset Apache-2.0.

The pinned OntoCheck import eagerly loads English stopwords, even for the selected offline metric functions. The adapter checks the English hash, restricts the NLTK search path to this directory and never downloads missing data during a run. No other languages, tokenizers or WordNet corpus are loaded.
