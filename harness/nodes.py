"""Turn a case into the node set every retriever searches over.

Every method — BM25, dense, hybrid, GraphRAG, the compiler — sees the same
nodes. That is what makes the comparison fair: no method gets a private view
of the data.

Granularity is the design decision here. Documents are one node each, but
**every chat message is its own node**. If the whole thread were a single
node, a system could retrieve it, drop the Hindi half when serialising, and
still score full marks on completeness — which is exactly the failure the
cross-lingual bucket exists to catch.
"""

from __future__ import annotations

from typing import Any

from benchmark.schema.models import Case, Node, PublicCase

# Node ids are stable per case, so gold facts can name them without knowing
# which case they came from.
INVOICE_ID = "INV"
EWAY_ID = "EWB"
ERP_ID = "ERP"
FLAG_ID = "FLAG"
TIMELINE_ID = "TIMELINE"


def case_to_nodes(case: Case | PublicCase) -> list[Node]:
    """Explode one case into its retrievable nodes.

    Args:
        case: A full or redacted case.

    Returns:
        Nodes in timeline order: documents first, then one per chat message.
    """
    data: dict[str, Any] = case.model_dump(mode="json")
    docs = data["documents"]
    inv = docs["invoice"]
    ref = inv["consignment_ref"]
    nodes: list[Node] = [
        Node(
            id=INVOICE_ID,
            type="Invoice",
            consignment_ref=ref,
            fields=inv,
            confidence=1.0,
            ts=inv["issued_at"],
            provenance=f"Tax invoice {inv['invoice_no']}",
        )
    ]

    if docs.get("eway_bill"):
        ewb = docs["eway_bill"]
        nodes.append(
            Node(
                id=EWAY_ID,
                type="EWayBill",
                consignment_ref=ref,
                fields=ewb,
                confidence=1.0,
                ts=ewb["generated_at"],
                provenance=f"E-way bill {ewb['ewb_no']}",
            )
        )

    erp = docs["erp_order"]
    nodes.append(
        Node(
            id=ERP_ID,
            type="ErpOrder",
            consignment_ref=ref,
            fields=erp,
            confidence=1.0,
            ts=erp["approval"]["approved_at"],
            provenance=f"Purchase order {erp['po_no']}",
        )
    )

    if docs.get("flag"):
        flag = docs["flag"]
        nodes.append(
            Node(
                id=FLAG_ID,
                type="Flag",
                consignment_ref=ref,
                fields=flag,
                confidence=1.0,
                ts=flag["raised_at"],
                provenance=f"Exception flag {flag['flag_id']}",
            )
        )

    nodes.append(
        Node(
            id=TIMELINE_ID,
            type="Timeline",
            consignment_ref=ref,
            fields={"events": data["events"]},
            confidence=1.0,
            ts=data["events"][0]["ts"] if data["events"] else None,
            provenance="Consignment event timeline",
        )
    )

    if docs.get("whatsapp_pod"):
        thread = docs["whatsapp_pod"]
        for message in thread["messages"]:
            nodes.append(
                Node(
                    id=message["msg_id"],
                    type="Message",
                    consignment_ref=ref,
                    fields=message,
                    confidence=1.0,
                    ts=message["ts"],
                    provenance=f"{thread['thread_name']} — {message['sender_name']}",
                )
            )

    return nodes


def render_context(nodes: list[Node]) -> str:
    """Serialise nodes into a citable ``[ID]``-tagged block.

    This is what leakage is measured against, so it must contain the literal
    field values rather than a summary of them.
    """
    blocks: list[str] = []
    for node in nodes:
        body = _render_fields(node.fields)
        blocks.append(f"[{node.id}] ({node.type} — {node.provenance})\n{body}")
    return "\n\n".join(blocks)


def _render_fields(value: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(value, dict):
        lines = []
        for key, val in value.items():
            if isinstance(val, dict | list):
                lines.append(f"{pad}{key}:")
                lines.append(_render_fields(val, indent + 1))
            else:
                lines.append(f"{pad}{key}: {val}")
        return "\n".join(lines)
    if isinstance(value, list):
        return "\n".join(_render_fields(item, indent) for item in value)
    return f"{pad}{value}"


def estimate_tokens(text: str) -> int:
    """Cheap token estimate.

    Deliberately a heuristic, not a tokenizer: the budget must mean the same
    thing for every method, and a shared approximation is fairer than each
    baseline importing whichever tokenizer its model ships with. Roughly four
    characters per token.
    """
    return max(1, len(text) // 4)
