# Zasada shadow_boundary_delta

Autor: Michal Machura

## Glowna zasada

W tabeli i w paperze glowna liczba nie jest:

\[
best\_score\_any\_graph(n)
\]

lecz:

\[
shadow\_boundary\_delta(R(a,b))
\]

## Definicja

Dla przypadku \(R(a,b)\):

\[
critical\_n = R(a,b)-1
\]

\[
boundary\_n = R(a,b)
\]

Niech:

\[
C_k^{a,b}
=
\{G : |V(G)|=k,\ score_{a,b}(G)=0\}
\]

czyli \(C_k^{a,b}\) jest zbiorem czystych rdzeni krytycznych.

Dla \(G \in C_k^{a,b}\) oraz \(x \in \{0,1\}^k\):

\[
\Phi_G(x)
=
\sum_{A \in R_{a-1}(G)}
\prod_{i \in A} x_i
+
\sum_{B \in B_{b-1}(G^c)}
\prod_{i \in B} (1-x_i)
\]

Definiujemy:

\[
\Delta_{a,b}(k \to k+1)
=
\min_{G \in C_k^{a,b}}
\min_{x \in \{0,1\}^k}
\Phi_G(x)
\]

Dla liczby Ramsey:

\[
shadow\_boundary\_delta(R(a,b))
=
\Delta_{a,b}(R(a,b)-1 \to R(a,b))
\]

## Regula metodologiczna

Do glownej tabeli wchodzi tylko wartosc:

\[
shadow\_boundary\_delta(R(a,b))
\]

Nie wolno zastapic jej dowolnym wynikiem:

\[
best\_score\_any\_graph(n)
\]

## Kandydat off-layer

Graf o niskim score na \(n=boundary\_n\), ale bez usuniecia wierzcholka dajacego czysty rdzen krytyczny, jest kandydatem off-layer.

Taki kandydat moze byc przydatny diagnostycznie, ale nie zastępuje wartosci:

\[
shadow\_boundary\_delta(R(a,b))
\]

## Przyklad R(3,7)

Dla \(R(3,7)\):

\[
critical\_n=22
\]

\[
boundary\_n=23
\]

\[
shadow\_boundary\_delta(R(3,7))=4
\]

Jezeli znaleziony graf na \(n=23\) ma niski score, ale nie posiada czystego usuniecia do \(n=22\), to jest off-layer i nie zastępuje wartosci \(4\).

## Przyklad R(5,5)

Dla \(R(5,5)\):

\[
critical\_n=42
\]

\[
boundary\_n=43
\]

\[
shadow\_boundary\_delta(R(5,5))=2
\]

To oznacza, ze czyste \(K43\) nie istnieje, poniewaz kazde rozszerzenie czystego \(K42\) tworzy co najmniej dwa konflikty \(K5\).

