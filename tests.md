## IMPORTANT — AUDIT ONLY

This is an **AUDIT / VERIFICATION task only**.

**DO NOT CHANGE ANYTHING.**

You must NOT:

* modify source code;
* modify tests;
* create or modify migrations;
* modify database schema;
* modify configuration;
* modify frontend;
* modify backend;
* fix bugs;
* refactor code;
* change data/business logic;
* add workarounds;
* commit changes;
* reset or revert existing changes.

Your job is strictly to **test, observe, calculate, compare, and report**.

If you find a bug, regression, inconsistency, suspicious behavior, or potential risk:

**DO NOT FIX IT.**

Instead, record it in the final report with:

```text
Severity: CRITICAL / HIGH / MEDIUM / LOW
Observed or suspected:
Affected area:
What happened:
Expected:
Actual:
Evidence:
```

You must leave the repository and running application in the exact state in which you found them, except for temporary test data required to perform the verification. Clean up only temporary test data created by your own audit where safe and practical.

If a test fails, **stop investigating that issue, collect evidence, and report it. Do not modify anything to make the test pass.**

The purpose of this task is to determine whether the current implementation is safe and correct, not to improve it.


Do not change any code.

Run a real end-to-end regression test focused only on the application's core financial/business logic using the actual running application, database, and realistic test users.

Do NOT run the full test suite.

## Priority

The most important things to verify are:

### 1. Groups

* create a group;
* add multiple members;
* verify membership and permissions;
* verify users cannot access groups they do not belong to.

### 2. Expenses

Create several realistic expenses with different:

* payers;
* amounts;
* participants;
* split configurations.

Verify:

* expense is persisted;
* payer is correct;
* participants are correct;
* split amounts are correct;
* the total of all splits matches the expense according to the existing business rules.

### 3. Balances

After creating the expenses, verify the resulting balances for every participant.

Check that:

* debts are assigned to the correct users;
* payer is credited correctly;
* no money appears/disappears;
* balances match the existing split logic.

### 4. Payments

Create real payments between users.

Verify:

* payment is persisted;
* payer/receiver are correct;
* payment amount is correct;
* balances change by the correct amount;
* paying one debt does not incorrectly affect unrelated debts;
* repeated/invalid payments are handled according to existing rules.

### 5. Payment optimization

This is critical.

Use a scenario where several people owe each other money and verify the application's payment/debt optimization algorithm.

For example, construct a situation with at least 3 users where direct debts create multiple obligations.

Verify:

* the optimized payment plan is mathematically correct;
* total money transferred is minimized according to the application's existing optimization rules;
* no participant pays more or receives less than their actual net balance;
* the optimized transactions settle all debts correctly;
* the algorithm does not create unnecessary payment cycles.

Compare the application's result with the expected net balances manually.

### 6. Regression after the new notification feature

Create a new expense that generates debt notifications.

Verify that:

* expense creation remains unchanged;
* split calculation remains unchanged;
* balances remain unchanged;
* payment optimization remains unchanged;
* notifications do not modify any financial values.

## Edge cases

Check at least a few important cases:

* payer is also a participant;
* uneven split amounts;
* multiple debtors;
* one user owes another user;
* several expenses between the same users;
* payment partially settling a debt;
* payment fully settling a debt;
* zero/invalid amounts where the existing API should reject them.

Do not invent new business rules. Follow the existing application's behavior.

## Verification method

Do not consider an HTTP 200/201 sufficient.

For each financial operation, verify the actual resulting database/API state and the numerical values.

For balances and payment optimization, explicitly calculate the expected result and compare it with the application's result.

## Risk report

After testing, provide a focused report of potential problems in the core financial logic, even if the tests pass.

Look specifically for:

* incorrect split calculations;
* rounding/cent errors;
* balance inconsistencies;
* duplicated debt;
* debt disappearing incorrectly;
* payment over-settlement;
* incorrect partial payments;
* optimization producing unnecessary transfers;
* optimization failing with 3+ users;
* order-dependent behavior;
* transaction/rollback problems;
* authorization leaks between groups;
* any regression caused by the notification feature.

For each issue report:
Severity: CRITICAL / HIGH / MEDIUM / LOW
Observed or suspected:
Affected area:
What could go wrong:
Do not fix anything during this test.

## Final report

Return:

### Core Financial E2E

PASS/FAIL for:

* Groups
* Expenses
* Splits
* Balances
* Payments
* Payment optimization
* Notification isolation

### Numerical Verification
Show the actual tested balances/debts and the expected values.

### Potential Problems

Only meaningful risks, not generic observations.

### Demo Readiness

Clearly state whether the core financial logic is safe for demo.

Do not modify code, tests, configuration, or database schema.
Do not run the full test suite.
Do not create a large new test suite.