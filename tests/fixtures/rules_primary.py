from penny.classify import contains, regexp, rule


@rule("Income:Salary")
def salary(tx):
    return regexp(tx.memo, r"payroll") and tx.amount_cents > 0


@rule("Travel:Hotel")
def hotel(tx):
    return contains(tx.payee, "hotel")


@rule("Shopping:GenericAmazon")
def amazon(tx):
    return contains(tx.payee, "amazon")
