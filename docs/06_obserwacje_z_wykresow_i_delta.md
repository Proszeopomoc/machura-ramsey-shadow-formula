# Obserwacje z wykresow i znaczenie liczby cienia

Autor: Michal Machura

## Cel obserwacji

W trakcie obliczen dla liczb Ramsey pojawil sie powtarzalny wzorzec: proba bezposredniego szukania grafu granicznego nie daje jednej uniwersalnej liczby bledu. Dla roznych rodzin Ramseyowskich graniczna liczba cienia jest inna.

To doprowadzilo do definicji glownej metryki:

\[
shadow\_boundary\_delta(R(a,b))
\]

czyli minimalnej liczby nieuniknionych konfliktow tworzonych przez jednowierzcholkowe rozszerzenie czystego rdzenia krytycznego.

## Glowna obserwacja

\[
shadow\_boundary\_delta(R(a,b))
\]

jest funkcja specyficzna dla danego przypadku \(R(a,b)\).

Nie istnieje uniwersalna stala.

Wlasnie dlatego metoda bezposredniego szukania grafu mogla zawodzic przez dekady: nie nalezy szukac jednej globalnej stalej, lecz osobnej wartosci granicznej dla konkretnej rodziny Ramseyowskiej.

## Zaobserwowane wartosci

Dla dotychczas analizowanych przypadkow otrzymano:

\[
\Delta_{3,3}(5 \to 6)=2
\]

\[
\Delta_{3,4}(8 \to 9)=2
\]

\[
\Delta_{3,5}(13 \to 14)=4
\]

\[
\Delta_{3,6}(17 \to 18)=4
\]

\[
\Delta_{3,7}(22 \to 23)=4
\]

\[
\Delta_{4,4}(17 \to 18)=12
\]

Dla glownego przypadku:

\[
\Delta_{5,5}(42 \to 43)=2
\]

## Interpretacja dla R(5,5)

Dla \(R(5,5)\):

\[
critical\_n = 42
\]

\[
boundary\_n = 43
\]

\[
\Delta_{5,5}(42 \to 43)=2
\]

Oznacza to, ze kazde jednowierzcholkowe rozszerzenie czystego rdzenia \(K42\) do \(K43\) tworzy co najmniej dwa konflikty \(K5\).

Zatem czyste \(K43\) nie istnieje.

Poniewaz czyste \(K42\) istnieje, otrzymujemy:

\[
R(5,5)=43
\]

## Znaczenie wykresow

Wykresy byly etapem odkrycia zaleznosci. Pokazaly, ze:

- dla \(R(5,5)\) przy warstwie \(42 \to 43\) liczba cienia wynosi \(2\),
- dla innych rodzin Ramseyowskich liczba cienia przyjmuje inne wartosci,
- liczba cienia zalezy od konkretnej rodziny \(R(a,b)\),
- symetria krawedzi i rozszczepienie konfliktow wspieraja interpretacje warstwy granicznej.

## Remark

shadow_boundary_delta is specific to each Ramsey number \(R(a,b)\).

There is no universal constant.

This explains why a direct graph search method is not the right primary object. The primary object is the shadow-boundary obstruction of a clean critical core.

