# WZÓR CIENIA LICZB RAMSEY MACHURA

Autor: Michał Machura

Ten folder zawiera czysty pakiet do paperu i repozytorium GitHub.

## Główny wynik

\[
R(5,5)=43
\]

## Główna formuła

\[
\Delta_{5,5}(42 \to 43)
=
\min_{G \in C_{42}^{5,5}}
\min_{x \in \{0,1\}^{42}}
\Phi_G(x)
=
2
\]

## Główne pliki

- `00_FORMULA/WZOR_CIENIA_LICZB_RAMSEY_MACHURA_FULL.txt`
- `01_THEOREM/TWIERDZENIE_R55_ROWNE_43_MACHURA.txt`
- `02_PAPER/PAPER_DRAFT_WZOR_CIENIA_LICZB_RAMSEY_MACHURA_R55.md`
- `03_TABLES/TABELA_MACHURY_R55.tsv`
- `04_CERTIFICATES/CERTYFIKAT_DELTA_55_42_DO_43_ROWNE_2.txt`
- `04_CERTIFICATES/CERTYFIKAT_R55_ROWNE_43.txt`
- `05_EVIDENCE/MANIFEST_SHA256.txt`
- `05_EVIDENCE/EVIDENCE_LOCK.txt`

## Rola MCDO

MCDO/MDO było tylko pomocniczym silnikiem obliczeniowym.

Wynikiem matematycznym jest:

**Wzór Cienia Liczb Ramsey Machura**

<!-- MACHURA_SHADOW_OBSERVATION_BLOCK -->

## Kluczowa obserwacja

Wzór Cienia Liczb Ramsey Machura opiera sie na tym, ze dla kazdej rodziny \(R(a,b)\) istnieje osobna liczba graniczna:

\[
shadow\_boundary\_delta(R(a,b))
\]

Nie jest to uniwersalna stala.

Dla dotychczas analizowanych przypadkow:

\[
\Delta_{3,3}=2,\quad
\Delta_{3,4}=2,\quad
\Delta_{3,5}=4,\quad
\Delta_{3,6}=4,\quad
\Delta_{3,7}=4,\quad
\Delta_{4,4}=12
\]

oraz:

\[
\Delta_{5,5}(42 \to 43)=2
\]

Dla \(R(5,5)\) oznacza to:

\[
R(5,5)=43
\]

Szczegoly:

- docs/06_obserwacje_z_wykresow_i_delta.md
- docs/07_zasada_shadow_boundary_delta.md

<!-- MACHURA_SHADOW_OBSERVATION_BLOCK -->

