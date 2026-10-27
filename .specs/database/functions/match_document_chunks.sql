create or replace function public.match_document_chunks(
  query_embedding vector(768),
  match_count int default 5
)
returns table (
  id int,
  document_id varchar,
  page_number int,
  chunk_text text,
  similarity float
)
language sql
stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.page_number,
    dc.chunk_text,
    1 - (dc.embedding <=> query_embedding) as similarity
  from public.document_chunks dc
  where dc.embedding is not null
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;
