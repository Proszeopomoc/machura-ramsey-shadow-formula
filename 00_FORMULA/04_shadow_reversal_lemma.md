LEMAT ODWRÓCENIA CIENIA
=======================

Autor: Michal Machura

Niech C_n^{a,b} oznacza zbior czystych rdzeni Ramseyowskich.

Niech chi : V(G) -> {red, blue} oznacza sposob polaczenia nowego
wierzcholka z rdzeniem G.

Niech G + chi oznacza graf po dodaniu nowego wierzcholka.

Definiujemy:

Conf_{a,b}(G)
=
RedK_a(G) union BlueK_b(G^c)

oraz:

Phi_{a,b,G}(chi)
=
zbior nowych konfliktow powstalych z udzialem dodanego wierzcholka.

Wzor przyrostu:

Conf_{a,b}(G + chi)
=
Conf_{a,b}(G) union Phi_{a,b,G}(chi)

Dla czystego rdzenia:

Conf_{a,b}(G) = empty

zatem:

Conf_{a,b}(G + chi) = Phi_{a,b,G}(chi)

Lemat odwrocenia:

C_{succ(n)}^{a,b} != empty

wtedy i tylko wtedy, gdy istnieje G in C_n^{a,b}
oraz istnieje chi : V(G) -> {red, blue}
takie, ze:

Phi_{a,b,G}(chi) = empty.

Dowod w przod:

Jesli istnieje para (G, chi) z pustym cieniem, to:

Conf(G + chi)
=
Conf(G) union Phi_G(chi)
=
empty union empty
=
empty

czyli G + chi jest czysty.

Dowod w tyl:

Jesli istnieje czysty graf H na succ(n) wierzcholkach,
to po usunieciu dowolnego wierzcholka v dostajemy czysty rdzen:

G = H - v

Kolory krawedzi z v do G definiuja chi.

Poniewaz H byl czysty, dodany wierzcholek nie tworzy zadnego konfliktu,
wiec:

Phi_G(chi) = empty.

Wniosek:

Szukanie czystego grafu na succ(n) jest rownowazne szukaniu
pustego cienia nad czystym rdzeniem na n.
