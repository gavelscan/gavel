"""RHJ official stock-token registry.

The issuer (Robinhood Assets, Jersey) publishes the canonical list of
stock tokens it has deployed. Membership in that list is the ONLY thing
that makes "verified official" true — a name is a claim, an address in
the issuer's registry is a fact.

Trust note: this introduces one off-chain dependency, and it is carried
openly. The registry is fetched from the issuer, cached to disk with a
timestamp, and every consumer distinguishes three states:

  member      — address is in a fresh registry           (fact: official)
  non-member  — address is abs