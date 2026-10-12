import json

import re

import sqlite3



from app.tools.finance_tools import (

    get_pending_transactions,

    process_payment,

    request_approval,

)

from app.tools.reconciliation import reconcile_transaction

from app.tools.verification import verify_payment

from app.tools.audit import log_action

from app.agent.llm_agent import understand_request

from app.tools.file_search import (

    search_files,

    format_search_results,

)



DATABASE = "data/financepilot.db"





class FinancePilotAgent:

    """Finance agent with separate search, review, and execution workflows."""



    def __init__(self):

        self.task = None

        self.plan = []

        self.execution_log = []



    # --------------------------------------------------------

    # LOGGING AND GOAL UNDERSTANDING

    # --------------------------------------------------------



    def log(self, message):

        self.execution_log.append(str(message))



    def understand_goal(self, user_request):

        self.task = user_request

        self.log(f"Goal received: {user_request}")

        return user_request



    def create_plan(self):

        self.plan = [

            "Find pending transactions",

            "Reconcile transactions against invoices",

            "Process transactions allowed by policy",

            "Request human approval when required",

            "Verify processed transactions",

            "Return execution summary",

        ]

        self.log("Execution plan created.")

        return self.plan



    def create_ai_plan(self, user_request):

        result = understand_request(user_request)



        self.task = result.get("goal", user_request)

        self.plan = result.get("actions", [])



        self.log(f"Goal understood: {self.task}")

        self.log("Plan created using the local planner.")



        return {

            "goal": self.task,

            "actions": self.plan,

        }



    # --------------------------------------------------------

    # FILE SEARCH

    # --------------------------------------------------------



    def search_company_files(self, query):

        """Search built-in company datasets."""

        self.log(f"Searching company files for: {query}")



        result = search_files(query)

        formatted_result = format_search_results(result)



        if result.get("success"):

            self.log(

                f"File search completed: "

                f"{result.get('total_matches', 0)} match(es)."

            )

        else:

            self.log(

                f"File search failed: "

                f"{result.get('reason', 'Unknown error')}"

            )



        return {

            "query": query,

            "result": result,

            "formatted_result": formatted_result,

        }



    def summarize_file_search(self, search_result):

        """Summarize search evidence without inventing facts."""

        if not search_result.get("success"):

            return search_result.get(

                "reason", "Unable to search company files."

            )



        matches = search_result.get("matches", [])



        if not matches:

            return (

                f"No company records were found for "

                f"'{search_result.get('query', '')}'."

            )



        lines = []



        for match in matches:

            source = match.get("source", "Unknown source")

            data = match.get("data", {})



            lines.append(f"Source: {source}")



            if match.get("reason"):

                lines.append(f"Finding: {match['reason']}")



            if isinstance(data, dict):

                for key, value in data.items():

                    lines.append(f"{key}: {value}")

            else:

                lines.append(str(data))



            lines.append("")



        return "\n".join(lines).strip()



    def run_file_search_task(self, user_request):

        """Search company files without executing financial actions."""

        query = user_request.strip()



        # Use a specific identifier when one is provided.

        identifier = re.search(

            r"\b(?:INV-\d+|TXN-?\d+)\b",

            query,

            re.IGNORECASE,

        )



        if identifier:

            query = identifier.group(0)



        search_result = self.search_company_files(query)

        raw_result = search_result.get("result", {})

        answer = self.summarize_file_search(raw_result)



        self.log("File-search task completed.")



        return {

            "goal": f"Search company files for: {query}",

            "mode": "read_only_search",

            "plan": [

                "Understand the search request",

                "Search the available company datasets",

                "Summarize the matching records",

                "Return source evidence",

            ],

            "answer": answer,

            "file_search": search_result,

            "execution": [],

            "verification": [],

            "execution_log": self.execution_log.copy(),

        }



    # --------------------------------------------------------

    # TRANSACTION RETRIEVAL

    # --------------------------------------------------------



    def get_transactions(self):

        """Retrieve transactions that are currently pending."""

        transactions = get_pending_transactions()

        self.log(

            f"Retrieved {len(transactions)} pending transaction(s)."

        )

        return transactions



    # --------------------------------------------------------

    # RECONCILIATION

    # --------------------------------------------------------



    def reconcile_transactions(self, transactions):

        """Evaluate each transaction against the finance policy."""

        results = []



        for transaction in transactions:

            if isinstance(transaction, dict):

                transaction_id = (

                    transaction.get("Transaction_id")

                    or transaction.get("transaction_id")

                )

            else:

                transaction_id = transaction[0] if transaction else None



            if not transaction_id:

                self.log("Skipped a record without a transaction ID.")

                continue



            result = reconcile_transaction(transaction_id)

            results.append(result)



            decision = result.get("decision", "UNKNOWN")

            reason = result.get("reason", "")



            self.log(

                f"{transaction_id}: {decision} - {reason}"

            )



            log_action(

                transaction_id,

                "Reconciliation",

                decision,

                reason,

            )



        return results



    # --------------------------------------------------------

    # PAYMENT EXECUTION AND APPROVAL

    # --------------------------------------------------------



    def execute_decisions(self, reconciliation_results):

        """Execute only policy-approved decisions."""

        execution_results = []



        for item in reconciliation_results:

            transaction_id = item.get("transaction_id")

            decision = item.get("decision")

            reason = item.get("reason", "")



            if not transaction_id:

                continue



            if decision == "AUTO_PROCESS":

                result = process_payment(transaction_id)

                execution_results.append(result)



                log_action(

                    transaction_id,

                    "Payment",

                    "PROCESSED" if result.get("success") else "FAILED",

                    result.get("reason", reason),

                )



                self.log(

                    f"{transaction_id}: Payment execution "

                    f"{'succeeded' if result.get('success') else 'failed'}."

                )



            elif decision == "APPROVAL_REQUIRED":

                result = request_approval(transaction_id)

                execution_results.append(result)



                log_action(

                    transaction_id,

                    "Approval Request",

                    "APPROVAL_REQUIRED",

                    result.get("reason", reason),

                )



                self.log(

                    f"{transaction_id}: Human approval required."

                )



            else:

                result = {

                    "success": False,

                    "transaction_id": transaction_id,

                    "action": "Review",

                    "reason": reason or "Transaction requires review.",

                }

                execution_results.append(result)



                self.log(

                    f"{transaction_id}: Not processed; review required."

                )



        return execution_results



    # --------------------------------------------------------

    # INDEPENDENT VERIFICATION

    # --------------------------------------------------------



    def verify_transactions(self, execution_results):

        """Verify every successful payment independently."""

        verification_results = []



        for result in execution_results:

            if (

                result.get("success") is True

                and result.get("action") == "Payment"

            ):

                transaction_id = result["transaction_id"]

                verification = verify_payment(transaction_id)

                verification_results.append(verification)



                if verification.get("verified"):

                    decision = "VERIFIED"

                    self.log(

                        f"{transaction_id}: Independently verified."

                    )

                else:

                    decision = "FAILED"

                    self.log(

                        f"{transaction_id}: Verification failed."

                    )



                log_action(

                    transaction_id,

                    "Verification",

                    decision,

                    verification.get("reason", ""),

                )



        return verification_results



    # --------------------------------------------------------

    # APPROVED TRANSACTIONS

    # --------------------------------------------------------



    
    def check_approved_transactions(self, transaction_id):
        """Process one approved transaction after rechecking policy."""
        conn = sqlite3.connect(DATABASE)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT b.transaction_id
                FROM bank_transactions AS b
                JOIN approvals AS a
                  ON a.transaction_id = b.transaction_id
                WHERE b.transaction_id = ?
                  AND b.status = 'Pending'
                  AND a.approval_id = (
                      SELECT MAX(a2.approval_id)
                      FROM approvals AS a2
                      WHERE a2.transaction_id = b.transaction_id
                  )
                  AND a.status = 'Approved'
                """,
                (transaction_id,),
            )
            approved_ids = [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

        if not approved_ids:
            reason = (
                "No latest approved approval request exists for this "
                "transaction, or it is no longer Pending."
            )
            self.log(f"{transaction_id}: {reason}")
            log_action(
                transaction_id,
                "Approved Payment Recheck",
                "BLOCKED",
                reason,
            )
            return [{
                "success": False,
                "transaction_id": transaction_id,
                "action": "Payment",
                "reason": reason,
            }]

        results = []

        for approved_id in approved_ids:
            try:
                check = reconcile_transaction(approved_id)
            except Exception as error:
                reason = f"Policy recheck failed: {error}"
                self.log(f"{approved_id}: {reason}; payment blocked.")
                log_action(
                    approved_id,
                    "Approved Payment Recheck",
                    "BLOCKED",
                    reason,
                )
                results.append({
                    "success": False,
                    "transaction_id": approved_id,
                    "action": "Payment",
                    "reason": reason,
                })
                continue

            if check.get("decision") != "APPROVAL_REQUIRED":
                reason = (
                    "Payment blocked because the latest policy check did "
                    "not confirm a valid high-value transaction requiring "
                    f"approval. Decision: {check.get('decision', 'UNKNOWN')}; "
                    f"reason: {check.get('reason', 'No reason provided')}"
                )
                self.log(f"{approved_id}: {reason}")
                log_action(
                    approved_id,
                    "Approved Payment Recheck",
                    "BLOCKED",
                    reason,
                )
                results.append({
                    "success": False,
                    "transaction_id": approved_id,
                    "action": "Payment",
                    "reason": reason,
                    "policy_check": check,
                })
                continue

            try:
                payment_result = process_payment(approved_id)
            except Exception as error:
                payment_result = {
                    "success": False,
                    "transaction_id": approved_id,
                    "action": "Payment",
                    "reason": f"Payment processing error: {error}",
                }

            results.append(payment_result)
            log_action(
                approved_id,
                "Approved Payment",
                "PROCESSED" if payment_result.get("success") else "FAILED",
                payment_result.get("reason", ""),
            )

            self.log(
                f"{approved_id}: Approved payment "
                f"{'processed' if payment_result.get('success') else 'failed'}."
            )

            if payment_result.get("success"):
                try:
                    verification = verify_payment(approved_id)
                except Exception as error:
                    verification = {
                        "verified": False,
                        "transaction_id": approved_id,
                        "reason": f"Verification error: {error}",
                    }

                results.append(verification)
                log_action(
                    approved_id,
                    "Verification",
                    "VERIFIED" if verification.get("verified") else "FAILED",
                    verification.get("reason", ""),
                )
                self.log(
                    f"{approved_id}: Post-payment verification "
                    f"{'passed' if verification.get('verified') else 'failed'}."
                )

        return results



    # --------------------------------------------------------

    # RECOVERY AND EXCEPTIONS

    # --------------------------------------------------------



    def recover_from_failures(self, reconciliation_results):

        """Record transactions requiring human investigation."""

        recovery_results = []



        for item in reconciliation_results:

            if item.get("decision") == "REVIEW":

                transaction_id = item.get("transaction_id")

                reason = item.get(

                    "reason",

                    "Transaction requires manual review.",

                )



                recovery = {

                    "transaction_id": transaction_id,

                    "reason": reason,

                    "action": "Human review required",

                    "policy_checklist": item.get("policy_checklist", {}),

                }

                recovery_results.append(recovery)



                log_action(

                    transaction_id,

                    "Recovery",

                    "REVIEW_REQUIRED",

                    json.dumps(recovery, default=str),

                )



                self.log(

                    f"{transaction_id}: Escalated for human review."

                )



        return recovery_results



    # --------------------------------------------------------

    # EXECUTION SUMMARY

    # --------------------------------------------------------



    def generate_execution_summary(

        self,

        reconciliation_results,

        execution_results,

        verification_results,

        recovery_results,

    ):

        decisions = [

            item.get("decision")

            for item in reconciliation_results

        ]



        processed = sum(

            1

            for item in execution_results

            if item.get("success") is True

            and item.get("action") == "Payment"

        )



        approval_required = decisions.count("APPROVAL_REQUIRED")

        review_required = decisions.count("REVIEW")



        verified = sum(

            1

            for item in verification_results

            if item.get("verified") is True

        )



        verification_failed = sum(

            1

            for item in verification_results

            if item.get("verified") is False

        )



        return {

            "total": len(reconciliation_results),

            "total_transactions": len(reconciliation_results),

            "processed": processed,

            "approval_required": approval_required,

            "review_required": review_required,

            "verified": verified,

            "verification_failed": verification_failed,

            "recovery_required": len(recovery_results),

        }



    # --------------------------------------------------------

    # READ-ONLY FINANCE REVIEW

    # --------------------------------------------------------



    def run_finance_review(self, user_request):

        """Classify pending transactions without executing payments."""

        self.log("Starting read-only finance review.")



        transactions = self.get_transactions()

        reconciliation_results = self.reconcile_transactions(transactions)



        explanations = [

            {

                "transaction_id": item.get("transaction_id"),

                "decision": item.get("decision"),

                "reason": item.get("reason"),

                "policy_checklist": item.get("policy_checklist", {}),

            }

            for item in reconciliation_results

        ]



        counts = {}

        for item in reconciliation_results:

            decision = item.get("decision", "UNKNOWN")

            counts[decision] = counts.get(decision, 0) + 1



        summary = {

            "total": len(reconciliation_results),

            "processed": 0,

            "approval_required": counts.get("APPROVAL_REQUIRED", 0),

            "review_required": counts.get("REVIEW", 0),

            "auto_process_eligible": counts.get("AUTO_PROCESS", 0),

            "note": "Read-only review. No payments were executed.",

        }



        self.log("Read-only finance review completed.")



        return {

            "goal": user_request,

            "mode": "finance_review",

            "plan": [

                "Retrieve pending transactions",

                "Compare transactions with invoice records",

                "Apply finance policy rules",

                "Explain each decision without executing payments",

            ],

            "reconciliation": reconciliation_results,

            "decision_explanations": explanations,

            "execution_summary": summary,

            "execution": [],

            "verification": [],

            "recovery": [],

            "execution_log": self.execution_log.copy(),

        }



    # --------------------------------------------------------

    # MAIN TASK ROUTER

    # --------------------------------------------------------



    def run_ai_task(self, user_request):

        """

        Route search, read-only review, and explicit execution safely.

        This method is part of FinancePilotAgent.

        """



        if not isinstance(user_request, str) or not user_request.strip():

            return {

                "goal": "",

                "mode": "clarification_required",

                "message": "Please enter a task or question.",

                "plan": [],

                "execution": [],

                "verification": [],

                "execution_log": [],

            }



        request = user_request.strip()

        q = request.casefold()

        self.execution_log = []

        self.understand_goal(request)



        # Explicit IDs are read-only by default, including IDs inside

        # a request that otherwise contains broad financial language.

        has_record_id = bool(

            re.search(r"\b(?:INV-\d+|TXN-?\d+)\b", request, re.IGNORECASE)

        )



        if has_record_id:

            return self.run_file_search_task(request)



        # Read-only wording must take priority over execution wording.

        read_only_phrases = (

            "without changing",

            "without processing",

            "do not process",

            "don't process",

            "read only",

            "read-only",

            "review all pending",

            "review pending transactions",

            "explain which transactions",

            "explain which ones",

            "which ones can be processed",

            "which transactions require approval",

            "which transactions need manual review",

            "explain why",

            "analyze pending transactions",

            "analyse pending transactions",

            "identify transactions that should be held",

            "without executing",

            "without making changes",

        )



        if any(phrase in q for phrase in read_only_phrases):

            return self.run_finance_review(request)



        # Execute only when the user explicitly asks for financial action.

        execution_phrases = (

            "process all pending payments",

            "process all pending transactions",

            "process all transactions",

            "process payments",

            "process payment",

            "execute payments",

            "execute payment",

            "reconcile all pending",

            "reconcile pending transactions",

            "reconcile all transactions",

            "reconcile pending payments",

            "reconcile pending",

        )



        if any(phrase in q for phrase in execution_phrases):

            plan_result = self.create_ai_plan(request)

            self.log("Starting explicitly requested finance execution.")



            transactions = self.get_transactions()

            reconciliation_results = self.reconcile_transactions(transactions)

            recovery_results = self.recover_from_failures(

                reconciliation_results

            )

            execution_results = self.execute_decisions(

                reconciliation_results

            )

            verification_results = self.verify_transactions(

                execution_results

            )



            summary = self.generate_execution_summary(

                reconciliation_results,

                execution_results,

                verification_results,

                recovery_results,

            )



            explanations = [

                {

                    "transaction_id": item.get("transaction_id"),

                    "decision": item.get("decision"),

                    "reason": item.get("reason"),

                    "policy_checklist": item.get("policy_checklist", {}),

                }

                for item in reconciliation_results

            ]



            self.log("Finance task execution finished.")



            return {

                "goal": plan_result["goal"],

                "mode": "finance_operation",

                "plan": plan_result["actions"],

                "reconciliation": reconciliation_results,

                "decision_explanations": explanations,

                "recovery": recovery_results,

                "execution": execution_results,

                "verification": verification_results,

                "execution_summary": summary,

                "execution_log": self.execution_log.copy(),

            }



        # General searches and questions never trigger payment execution.

        return self.run_file_search_task(request)

