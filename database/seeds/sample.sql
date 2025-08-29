-- database/seeds/sample.sql
INSERT INTO textbook_chunks (book_title, section, chunk_idx, body, embedding)
VALUES ('Kinase Handbook', 'Intro', 0, 'Kinases are...', ARRAY[0.0, 0.1, 0.2]::vector);