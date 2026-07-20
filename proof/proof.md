# The Who-Provenance Framework

## The Blame-Frame Semiring

An *interval* takes the right-open form $[a,b)$ and represents the set $\{x \in \mathbb{N} \cup \{\infty\} \mid a \le x < b\}$. A *timeline* is a finite set of non-overlapping intervals, denoted by $T$, where empty intervals are implicit and can be omitted. The power set of all timelines is denoted by $\mathcal{T}$. When the intervals of a timeline describe periods of tuple presence, its complement is naturally periods of tuple absence. To attribute responsibility, or blame, we replace each interval in a timeline with a triple we call a *blame frame*, consisting of the interval itself and blame information. A *blame timeline* is a finite set of blame-frames, denoted $T_F$, whose underlying intervals form a timeline, that is, $\{I \mid F \in T_F\} \in \mathcal{T}$. The set of all blame timelines is denoted by $\mathcal{T}_\mathcal{F}$.

> **Definition 1.** Let $\mathcal{M}^+ = (M^+, \otimes_+, 1_+)$ and $\mathcal{M}^- = (M^-, \otimes_-, 1_-)$ be commutative monoids. A *blame-frame* is a triple $F := (I,m^+,m^-)$, where $I$ is an interval, $m^+ \in M^+$ is the *positive blame*, and $m^- \in M^-$ is the *negative blame*. $m^+$ provides blame information of the interval of presence $I$, and $m^-$ of the interval of absence that immediately follows. Intuitively, a blame frame is an interval with meta information. Note that any period of absence preceding the earliest interval of presence in a timeline cannot be represented, and is the default state rather than the result of any action.

We define the *blame-frame intersection* operator, denoted $\cap_F$. The operator acts componentwise: the interval component is given by standard interval intersection, while the blame components are combined according to their corresponding monoid operators:

$$(I_0, m_0^+, m_0^-) \cap_F (I_1, m_1^+, m_1^-) := (I_0 \cap I_1, m_0^+ \otimes_{+} m_1^+, m_0^- \otimes_{-} m_1^-)$$

> **Definition 2.** The *blame-frame semiring* $\mathcal{B} = (\mathcal{P}(\mathcal{T}_\mathcal{F}), \oplus_\mathcal{B}, \otimes_\mathcal{B}, 0, 1)$ is built as follows:
> * $P \oplus_\mathcal{B} Q := P \cup Q$
> * $P \otimes_\mathcal{B} Q := \{U \cap_F V \mid U \in P, V \in Q, I(U) \cap I(V) \neq \emptyset\}$
> * $0 := \emptyset$
> * $1 := \{([0,\infty), 1_{+}, 1_{-})\}$
> 
> 
> Where $(M^+, \otimes_{+}, 1_{+})$ and $(M^-, \otimes_{-}, 1_{-})$ are commutative monoids and $I(F)$ projects the interval component of a blame-frame $F$. $\otimes_\mathcal{B}$ can be understood as the pairwise intersection of blame-frame timelines.

> **Lemma 1.** $\mathcal{B}$ is a commutative semiring.

---

### Proof of Lemma 1

We verify the semiring axioms. Let $P, Q, R \in \mathcal{B}$.

#### Additive Commutative Monoid $(\mathcal{B}, \oplus_\mathcal{B}, 0)$

$\oplus_\mathcal{B}$ is defined as standard set union $\cup$. By standard definition in set theory, set union is associative and commutative. Since $P \cup \emptyset = P$, the empty set is the identity element. Thus, $(\mathcal{B}, \oplus_\mathcal{B}, 0)$ is a commutative monoid.

#### Multiplicative Commutative Monoid $(\mathcal{B}, \otimes_\mathcal{B}, 1)$

We verify the commutativity, associativity, and identity element of the multiplicative operator.

Commutativity of $\cap_F$ follows from the commutativity of standard set intersection under the set-theoretic definition of intervals, and the commutativity of $\otimes_{+}$ and $\otimes_{-}$ in their respective monoids. For any blame-frames $F_0 = (I_0, m_0^+, m_0^-)$, $F_1 = (I_1, m_1^+, m_1^-)$, and $F_2 = (I_2, m_2^+, m_2^-)$:

$$\begin{aligned} F_0 \cap_F F_1 &= (I_0 \cap I_1,\ m_0^+ \otimes_{+} m_1^+,\ m_0^- \otimes_{-} m_1^-) \\ &= (I_1 \cap I_0,\ m_1^+ \otimes_{+} m_0^+,\ m_1^- \otimes_{-} m_0^-) \\ &= F_1 \cap_F F_0 \end{aligned}$$

Consequently, commutativity of $\otimes_\mathcal{B}$ follows:

$$\begin{aligned} P \otimes_\mathcal{B} Q &= \{U \cap_F V \mid U \in P, V \in Q, I(U) \cap I(V) \neq \emptyset\} \\ &= \{V \cap_F U \mid U \in P, V \in Q, I(V) \cap I(U) \neq \emptyset\} \\ &= Q \otimes_\mathcal{B} P \end{aligned}$$

Associativity of $\cap_F$ similarly follows from the associativity of standard set intersection and of the monoid operations $\otimes_{+}$ and $\otimes_{-}$:

$$\begin{aligned} (F_0 \cap_F F_1) \cap_F F_2 &= \big((I_0 \cap I_1) \cap I_2,\ (m_0^+ \otimes_{+} m_1^+) \otimes_{+} m_2^+,\ (m_0^- \otimes_{-} m_1^-) \otimes_{-} m_2^-\big) \\ &= \big(I_0 \cap (I_1 \cap I_2),\ m_0^+ \otimes_{+} (m_1^+ \otimes_{+} m_2^+),\ m_0^- \otimes_{-} (m_1^- \otimes_{-} m_2^-)\big) \\ &= F_0 \cap_F (F_1 \cap_F F_2) \end{aligned}$$

Associativity of $\otimes_\mathcal{B}$ follows as such:

$$\begin{aligned} (P \otimes_\mathcal{B} Q) \otimes_\mathcal{B} R &= \{(U \cap_F V) \cap_F W \mid U \in P, V \in Q, W \in R, (I(U) \cap I(V)) \cap I(W) \neq \emptyset\} \\ &= \{U \cap_F (V \cap_F W) \mid U \in P, V \in Q, W \in R, I(U) \cap (I(V) \cap I(W)) \neq \emptyset\} \\ &= P \otimes_\mathcal{B} (Q \otimes_\mathcal{B} R) \end{aligned}$$

For any blame-frame $F = (I, m^+, m^-)$, since $I \subseteq [0, \infty)$ by definition, we have $I \cap [0, \infty) = I$. Moreover, $1_{+}$ and $1_{-}$ are the identity elements of their respective monoids. Thus:

$$\begin{aligned} F \cap_F ([0, \infty), 1_{+}, 1_{-}) &= (I \cap [0, \infty),\ m^+ \otimes_{+} 1_{+},\ m^- \otimes_{-} 1_{-}) \\ &= (I, m^+, m^-) \\ &= F \end{aligned}$$

Therefore:

$$\begin{aligned} P \otimes_\mathcal{B} 1 &= \{U \cap_F ([0, \infty), 1_{+}, 1_{-}) \mid U \in P, I(U) \cap [0, \infty) \neq \emptyset\} \\ &= \{U \mid U \in P\} \\ &= P \end{aligned}$$

Thus, $1 = \{([0, \infty), 1_{+}, 1_{-})\}$ is the multiplicative identity.

#### Annihilation

We show that $P \otimes_\mathcal{B} 0 = 0$. By definition,

$$\begin{aligned} P \otimes_\mathcal{B} \emptyset &= \{U \cap_F V \mid U \in P, V \in \emptyset, I(U) \cap I(V) \neq \emptyset\} \\ &= \emptyset \end{aligned}$$

since no such $V$ exists.

#### Multiplication Distributes Over Addition

We verify the left-distributivity of $\otimes_\mathcal{B}$ over $\oplus_\mathcal{B}$. By the definition of standard set union, $A \cup B = \{x \mid x \in A \lor x \in B\}$:

$$\begin{aligned} P \otimes_\mathcal{B} (Q \oplus_\mathcal{B} R) &= \{U \cap_F V \mid U \in P, V \in (Q \cup R), I(U) \cap I(V) \neq \emptyset\} \\ &= \{U \cap_F V \mid U \in P, (V \in Q \lor V \in R), I(U) \cap I(V) \neq \emptyset\} \\ &= \{U \cap_F V \mid U \in P, V \in Q, I(U) \cap I(V) \neq \emptyset\} \\ &\quad \cup \{U \cap_F V \mid U \in P, V \in R, I(U) \cap I(V) \neq \emptyset\} \\ &= (P \otimes_\mathcal{B} Q) \oplus_\mathcal{B} (P \otimes_\mathcal{B} R) \end{aligned}$$

Right-distributivity follows directly from the commutativity of $\otimes_\mathcal{B}$. $\blacksquare$