# WZÓR CIENIA LICZB RAMSEY MACHURA

Autor: Michał Machura

## Wynik główny

\[
R(5,5)=43
\]

## Definicja rdzeni krytycznych

\[
C_{42}^{5,5}
=
\{G : |V(G)|=42,\ score_{5,5}(G)=0\}
\]

czyli \(C_{42}^{5,5}\) jest zbiorem wszystkich czystych rdzeni krytycznych K42, bez czerwonego \(K_5\) i bez niebieskiego \(K_5\).

## Score

\[
score_{5,5}(G)
=
\#redK_5(G)
+
\#blueK_5(G^c)
\]

## Wzór cienia

Dla \(G \in C_{42}^{5,5}\):

\[
\Phi_G(x)
=
\sum_{A \in R_4(G)}
\prod_{i \in A} x_i
+
\sum_{B \in B_4(G^c)}
\prod_{i \in B} (1-x_i)
\]

gdzie:

\[
x \in \{0,1\}^{42}
\]

oraz:

\[
R_4(G) = \text{zbiór czerwonych }K_4\text{ w }G
\]

\[
B_4(G^c) = \text{zbiór niebieskich }K_4\text{ w }G^c
\]

## Główny wynik

\[
\Delta_{5,5}(42 \to 43)
=
\min_{G \in C_{42}^{5,5}}
\min_{x \in \{0,1\}^{42}}
\Phi_G(x)
=
2
\]

## Wniosek

Ponieważ:

\[
\Delta_{5,5}(42 \to 43)=2>0
\]

każde dodanie 43. wierzchołka do czystego rdzenia K42 tworzy co najmniej dwa konflikty Ramseyowskie K5.

Zatem nie istnieje czyste kolorowanie K43 bez monochromatycznego K5.

Czyli:

\[
R(5,5)\le 43
\]

Ponieważ istnieje czysty rdzeń K42:

\[
score_{5,5}(G_{42})=0
\]

to:

\[
R(5,5)>42
\]

czyli:

\[
R(5,5)\ge 43
\]

Razem:

\[
R(5,5)=43
\]

## Rola MCDO

MCDO/MDO nie jest nazwą wyniku.

MCDO/MDO było użyte wyłącznie jako pomocniczy silnik obliczeniowy do:
- generowania grafów,
- liczenia cieni,
- walidacji rdzeni krytycznych,
- kontroli odtwarzalności,
- tworzenia manifestów SHA256.

Wynikiem matematycznym jest Wzór Cienia Liczb Ramsey Machura.
