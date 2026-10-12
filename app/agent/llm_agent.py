def understand_request(user_request):

    request = user_request.lower()

    if "reconcile" in request and "pending" in request:

        return {
            "goal": "Reconcile pending transactions",
            "actions": [
                "Find pending transactions",
                "Reconcile transactions against invoices",
                "Process transactions allowed by policy",
                "Request human approval when required",
                "Verify processed transactions",
                "Return execution summary"
            ]
        }

    return {
        "goal": user_request,
        "actions": [
            "Understand the request",
            "Determine required actions",
            "Execute approved actions",
            "Verify the outcome",
            "Return a summary"
        ]
    }