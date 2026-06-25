alter table public.documents
add column if not exists page_count integer;

alter table public.document_chunks
add column if not exists page_number integer;

create index if not exists document_chunks_document_page_index
on public.document_chunks (document_id, page_number, chunk_index);
