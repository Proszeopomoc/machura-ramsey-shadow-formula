# Core Formula for R(5,5)

Author: Michał Machura

Method:
Wzór Cienia Liczb Ramsey Machura / Machura Ramsey Shadow Formula

## Critical core layer

```text
C_{42}^{5,5}
=
{ G : |V(G)| = 42, score_{5,5}(G) = 0 }
```

This is the layer of all clean critical (5,5,42)-graphs.

Equivalently:

```text
score_{5,5}(G)
=
# red K5 in G
+
# blue K5 in G^c
= 0
```

## One-vertex extension vector

```text
x in {0,1}^{42}
```

where:

```text
x_i = 1  means the new vertex connects red to vertex i
x_i = 0  means the new vertex connects blue to vertex i
```

## Machura shadow

For G in C_{42}^{5,5}:

```text
Phi_G(x)
=
sum over A in R_4(G) of product over i in A of x_i
+
sum over B in B_4(G^c) of product over i in B of (1 - x_i)
```

where:

```text
R_4(G)   = set of red K4 shadows in G
B_4(G^c) = set of blue K4 shadows in G^c
```

## Boundary value

```text
Delta_{5,5}(42 -> 43)
=
min over G in C_{42}^{5,5}
min over x in {0,1}^{42}
Phi_G(x)
=
2
```

## Consequence

```text
Delta_{5,5}(42 -> 43) = 2 > 0
```

Therefore every one-vertex extension from a clean K42 critical core to K43 creates at least two K5 conflicts.

Hence no clean K43 exists.

Since a clean K42 exists:

```text
R(5,5) = 43
```
