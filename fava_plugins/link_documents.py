"""Beancount plugin to link entries to documents.

It goes through all entries with a `document` metadata-key, and tries to
associate them to Document entries. For transactions, it then also adds a link
from the transaction to documents, as well as the "#linked" tag.
"""
from __future__ import annotations

from collections import defaultdict
from os.path import basename
from os.path import dirname
from os.path import join
from os.path import normpath
from typing import Any

from beancount.core.compare import hash_entry
from beancount.core.data import Document
from beancount.core.data import Entries
from beancount.core.data import Transaction

from fava.core import FavaLedger
from fava.beans.account import get_entry_accounts
from fava.helpers import BeancountError
from fava.util.sets import add_to_set


class DocumentError(BeancountError):
    """Document-linking related error."""


__plugins__ = ["link_documents"]


def link_documents(
    entries: Entries, _: Any
) -> tuple[Entries, list[DocumentError]]:
    """Link entries to documents."""

    errors = []

    # All document indices by their file basename.
    by_basename = defaultdict(list)

    for index, entry in enumerate(entries):
        if isinstance(entry, Document):
            by_basename[basename(entry.filename)].append((index, entry, hash_entry(entry)[0:8]))

    for index, entry in enumerate(entries):
        # Only transactions are relevant
        if not isinstance(entry, Transaction):
            continue

        # Check there's at least one "document" metadata
        disk_docs = [
            value
            for key, value in entry.meta.items()
            if key.startswith("document")
        ]
        for posting in entry.postings:
            if posting.meta:
                for key, value in posting.meta.items():
                    if key.startswith("document"):
                        disk_docs.append(value)
        if not disk_docs:
            continue

        # Loop over the linked documents
        entry_accounts = get_entry_accounts(entry)
        for disk_doc in disk_docs:
            # Check document exists
            documents = [
                (j, h)
                for j, document, h in by_basename[disk_doc]
                if any(document.account in account for account in entry_accounts)
            ]

            if not documents:
                errors.append(
                    DocumentError(
                        entry.meta,
                        f"Document not found: '{disk_doc}'",
                        entry,
                    )
                )
                continue

            # Add links
            for j, h in documents:
                # Add link to document if not linked already
                doc: Document = entries[j]  # type: ignore
                if "linked" not in doc.tags:
                    entries[j] = doc._replace(
                        links=add_to_set(doc.links, h),
                        tags=add_to_set(doc.tags, "linked"),
                    )

                # Add link to transaction
                transaction: Transaction = entries[index]
                entries[index] = transaction._replace(links=add_to_set(transaction.links, h))

    return entries, errors
