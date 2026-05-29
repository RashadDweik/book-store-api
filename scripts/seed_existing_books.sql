-- Seed existing books into the books table and assign category ids directly.
-- Run this after seed_authors.sql, seed_categories.sql, and seed_books.sql if you
-- use the separate base seed files; otherwise this can be used as a standalone
-- import for the existing catalog dataset.

BEGIN;

CREATE TEMP TABLE book_seed (
  isbn text PRIMARY KEY,
  title text NOT NULL,
  author_name text NOT NULL,
  release_year int NOT NULL,
  description text NOT NULL,
  category_id uuid NOT NULL
) ON COMMIT DROP;

INSERT INTO book_seed (isbn, title, author_name, release_year, description, category_id)
VALUES
  ('0434006107', $q$The Hobbit$q$, $q$J.R.R. Tolkien$q$, 1966, $q$Bilbo Baggins is a comfortable, unambitious hobbit whose life is turned upside down when the wizard Gandalf and a company of thirteen dwarves whisk him away on a journey to reclaim a stolen treasure from the dragon Smaug.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0451524934', $q$1984$q$, $q$George Orwell$q$, 1961, $q$Set in a terrifyingly bureaucratic totalitarian state, this dystopian masterpiece follows Winston Smith as he attempts to rebel against the all-seeing Big Brother and the thought-controlling Inner Party.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0684801523', $q$The Great Gatsby$q$, $q$F. Scott Fitzgerald$q$, 1995, $q$A portrait of the Roaring Twenties, the novel chronicles narrator Nick Carraway's interactions with his mysterious, wealthy neighbor Jay Gatsby, who is desperately obsessed with reuniting with his former love, Daisy Buchanan.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0446310786', $q$To Kill a Mockingbird$q$, $q$Harper Lee$q$, 1988, $q$Set in a racially fractured Alabama town during the Great Depression, the story is seen through the eyes of young Scout Finch as her lawyer father, Atticus, defends a Black man falsely accused of a terrible crime.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0316769177', $q$The Catcher in the Rye$q$, $q$J.D. Salinger$q$, 1951, $q$This quintessential novel of teenage angst follows Holden Caulfield, a disillusioned sixteen-year-old student, over a series of lonely, wandering days in New York City after being expelled from his prep school.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0399501487', $q$Lord of the Flies$q$, $q$William Golding$q$, 1959, $q$A plane crash leaves a group of schoolboys stranded on a deserted island. As they attempt to govern themselves, their fragile, makeshift civilization collapses into savage brutality and primal survival instincts.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0141439513', $q$Pride and Prejudice$q$, $q$Jane Austen$q$, 2002, $q$Set in 19th-century England, this classic romantic comedy of manners charts the turbulent relationship between the spirited Elizabeth Bennet and the wealthy, aristocratically proud Mr. Darcy.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0451526341', $q$Animal Farm$q$, $q$George Orwell$q$, 1996, $q$A political allegory disguised as a fairy tale, tracing a revolution by farm animals who overthrow their human master, only to watch their new society slowly devolve into a brutal dictatorship led by pigs.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0140177396', $q$Of Mice and Men$q$, $q$John Steinbeck$q$, 1993, $q$A tragic story of two displaced migrant ranch workers, George Milton and the physically powerful yet mentally disabled Lennie Small, navigating the harsh economic realities of the Dust Bowl era in California.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0143039431', $q$The Grapes of Wrath$q$, $q$John Steinbeck$q$, 2006, $q$This epic American realism novel follows the Joad family, a poor clan of tenant farmers driven from their Oklahoma home by economic hardship, agricultural shifts, and the devastating Dust Bowl.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0141441143', $q$Jane Eyre$q$, $q$Charlotte Brontë$q$, 2006, $q$The moving narrative of an orphaned young woman who overcomes a harsh upbringing to become a governess at Thornfield Hall, where she falls deeply in love with her brooding, mysterious employer, Edward Rochester.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0141439556', $q$Wuthering Heights$q$, $q$Emily Brontë$q$, 2002, $q$A dark, gothic tale of passion and revenge centered on the intense, destructive love between the orphan Heathcliff and Catherine Earnshaw on the isolated, storm-swept Yorkshire moors.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0141439572', $q$The Picture of Dorian Gray$q$, $q$Oscar Wilde$q$, 2003, $q$A philosophical tale of a young man who sells his soul so that his physical appearance remains forever youthful, while a painted portrait hidden in his attic bears the grotesque scars of his moral decay.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0140268863', $q$The Odyssey$q$, $q$Homer$q$, 1997, $q$The epic Greek journey of Odysseus, king of Ithaca, who faces mythical monsters, vengeful gods, and treacherous seas during his ten-year struggle to return home to his wife and son after the fall of Troy.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),
  ('0684801221', $q$The Old Man and the Sea$q$, $q$Ernest Hemingway$q$, 1995, $q$A stark, beautifully written short novel that tells the story of Santiago, an aging Cuban fisherman, and his grueling, multi-day battle out in the Gulf Stream with a giant, majestic marlin.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000001'),

  ('0590353403', $q$Harry Potter & the Sorcerer's Stone$q$, $q$J.K. Rowling$q$, 1998, $q$On his eleventh birthday, an unloved orphan discovers he is actually a wizard and is invited to attend Hogwarts School of Witchcraft and Wizardry, uncovering a magical world tied to his mysterious past.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0345342968', $q$Fahrenheit 451$q$, $q$Ray Bradbury$q$, 1953, $q$In a dystopian future where books are outlawed and systematically burned by "firemen," Guy Montag begins to question his destructive role after meeting a young neighbor who dares to think freely.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0345339703', $q$The Fellowship of the Ring$q$, $q$J.R.R. Tolkien$q$, 1986, $q$The epic opening chapter of the war for Middle-earth, following young hobbit Frodo Baggins as he inherits the Dark Lord Sauron's One Ring and forms an alliance to carry it to the fires of Mount Doom.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0060850523', $q$Brave New World$q$, $q$Aldous Huxley$q$, 2006, $q$A chillingly prophetic vision of a futuristic "World State" where citizens are genetically engineered, socially conditioned, and chemically medicated into a painless, superficial, and compliant existence.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0441172717', $q$Dune$q$, $q$Frank Herbert$q$, 1990, $q$Set on the harsh desert planet Arrakis, this sci-fi masterpiece chronicles young Paul Atreides as his noble family is betrayed, forcing him into a sweeping battle for control of the universe's rarest substance: the spice melange.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0141439475', $q$Frankenstein$q$, $q$Mary Shelley$q$, 2003, $q$Driven by scientific ambition, Victor Frankenstein reanimates dead matter to form a living creature. Horrified by his monstrous creation, he abandons it, sparking a tragic chain of loneliness and bloody revenge.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0486411095', $q$Dracula$q$, $q$Bram Stoker$q$, 2000, $q$The foundational gothic horror novel told through letters and journals, detailing Count Dracula's sinister voyage from his castle in Transylvania to England to feed on fresh blood and expand his undead empire.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0786856297', $q$The Lightning Thief$q$, $q$Rick Riordan$q$, 2005, $q$Twelve-year-old Percy Jackson discovers he is actually a demigod son of Poseidon. When Zeus's master lightning bolt is stolen, Percy is accused of the crime and must go on a cross-country quest to find the real thief.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0439023483', $q$The Hunger Games$q$, $q$Suzanne Collins$q$, 2008, $q$In the dystopian ruins of Panem, sixteen-year-old Katniss Everdeen takes her younger sister's place in a mandatory, televised survival deathmatch engineered by the wealthy, tyrannical Capitol.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0439023491', $q$Catching Fire$q$, $q$Suzanne Collins$q$, 2009, $q$Following her unexpected victory in the Hunger Games, Katniss Everdeen's act of defiance sparks unrest across the districts, forcing the Capitol to target her in a special championship edition of the games.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0439023513', $q$Mockingjay$q$, $q$Suzanne Collins$q$, 2010, $q$Katniss Everdeen survives the Quarter Quell and is taken to the underground District 13, where she reluctantly becomes the symbolic figurehead of a full-scale rebellion to overthrow President Snow and the Capitol.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0375831002', $q$The Book Thief$q$, $q$Markus Zusak$q$, 2006, $q$Narrated by Death, this historical novel follows Liesel Meminger, a young girl growing up in Nazi Germany who finds solace in stealing books and sharing them with her neighbors and the Jewish man hidden in her basement.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('037582345X', $q$The Golden Compass$q$, $q$Philip Pullman$q$, 2002, $q$Young Lyra Belacqua lives in a parallel universe where human souls exist outside the body as animal companions. When her friend is kidnapped, she embarks on an arctic expedition to uncover a sinister scientific conspiracy.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0812550706', $q$Ender's Game$q$, $q$Orson Scott Card$q$, 1994, $q$To prepare for a future alien invasion, Earth's military recruits child prodigy Ender Wiggin into an orbital Battle School, pushing him through increasingly brutal psychological warfare simulations.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),
  ('0441569595', $q$Neuromancer$q$, $q$William Gibson$q$, 1984, $q$The seminal cyberpunk novel tracking Case, a burned-out console cowboy and data thief, who is hired by a mysterious employer for a final hack against an unthinkably powerful artificial intelligence matrix.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000002'),

  ('0345503804', $q$The Shining$q$, $q$Stephen King$q$, 2008, $q$Jack Torrance takes a job as the winter caretaker at the isolated Overlook Hotel. As heavy snows lock them in, the hotel's dark, supernatural forces slowly drive Jack insane, endangering his family.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),
  ('0385504209', $q$The Da Vinci Code$q$, $q$Dan Brown$q$, 2003, $q$Symbologist Robert Langdon is called to the Louvre after a curator is murdered, uncovering a trail of hidden clues in Leonardo da Vinci's paintings that point to a massive, centuries-old religious cover-up.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),
  ('0671027360', $q$Angels & Demons$q$, $q$Dan Brown$q$, 2001, $q$Robert Langdon races through Rome and the Vatican to stop an ancient secret brotherhood, the Illuminati, from detonating a stolen canister of highly destructive antimatter over the papal enclave.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),
  ('030758836X', $q$Gone Girl$q$, $q$Gillian Flynn$q$, 2012, $q$On his fifth wedding anniversary, Nick Dunne becomes the prime suspect after his wife, Amy, suddenly vanishes. Through alternating journal entries, a deeply toxic and calculated game of manipulation unfolds.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),
  ('0307269752', $q$The Girl with the Dragon Tattoo$q$, $q$Stieg Larsson$q$, 2008, $q$Disgraced journalist Mikael Blomkvist teams up with the brilliant, anti-social computer hacker Lisbeth Salander to investigate the forty-year-old disappearance of a wealthy industrialist's niece.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),
  ('0525478817', $q$The Fault in Our Stars$q$, $q$John Green$q$, 2012, $q$Sixteen-year-old Hazel Lancaster, a terminal thyroid cancer patient, undergoes a life-changing romance after meeting Augustus Waters, a charismatic former basketball player, at her support group.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),
  ('0151008116', $q$Life of Pi$q$, $q$Yann Martel$q$, 2001, $q$Following a catastrophic shipwreck in the Pacific Ocean, a young Indian boy named Pi Patel finds himself stranded on a lone lifeboat with an unusual companion: a fierce 450-pound Bengal tiger named Richard Parker.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),
  ('1594480001', $q$The Kite Runner$q$, $q$Khaled Hosseini$q$, 2004, $q$Set against the backdrop of a changing Afghanistan, the story follows Amir, a young boy from Kabul, who betrays his closest childhood friend, a decision that haunts him into adulthood until a chance for redemption arises.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),
  ('1594489505', $q$A Thousand Splendid Suns$q$, $q$Khaled Hosseini$q$, 2007, $q$A powerful tale chronicling thirty years of volatile Afghan history, focusing on the intersecting lives of Mariam and Laila, two women forced into a cruel marriage who form an unbreakable, supportive bond.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),
  ('0739326224', $q$Memoirs of a Geisha$q$, $q$Arthur Golden$q$, 2005, $q$The captivating fictional memoir of Nitta Sayuri, a young girl sold from her fishing village into an elite geisha house in pre-World War II Kyoto, where she learns the intricate, demanding arts of entertainment.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000003'),

  ('0061122416', $q$The Alchemist$q$, $q$Paulo Coelho$q$, 2006, $q$An inspirational fable tracking Santiago, an Andalusian shepherd boy, who journeys to the Egyptian pyramids in search of a worldly treasure, learning instead to listen to his heart and follow his Personal Legend.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004'),
  ('0156012197', $q$The Little Prince$q$, $q$Antoine de Saint-Exupéry$q$, 2000, $q$After crashing in the Sahara Desert, a pilot meets a small prince who traveled from a distant asteroid, exploring themes of loneliness, love, and the profound, often absurd nature of adulthood.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004'),
  ('0062316095', $q$Sapiens$q$, $q$Yuval Noah Harari$q$, 2015, $q$A sweeping historical narrative tracing the development of Homo sapiens from insignificant stone-age apes to the dominant rulers of planet Earth, driven by the unique ability to believe in shared, imagined myths.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004'),
  ('0399590501', $q$Educated$q$, $q$Tara Westover$q$, 2018, $q$A memoir documenting a young woman's journey from growing up isolated in an extremist survivalist family in rural Idaho to stepping into a classroom for the first time at age seventeen and eventually earning a PhD.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004'),
  ('0374275637', $q$Thinking, Fast and Slow$q$, $q$Daniel Kahneman$q$, 2011, $q$A tour of the human mind by a Nobel laureate, mapping the two cognitive systems that drive decisions: System 1 (fast, intuitive, and emotional) and System 2 (slow, deliberate, and logical).$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004'),
  ('0671708635', $q$The 7 Habits of Highly Effective People$q$, $q$Stephen R. Covey$q$, 1990, $q$A timeless self-improvement framework centered on aligning actions with universal character principles, shifting readers from dependence to independence, and ultimately to high-functioning interdependence.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004'),
  ('0307352145', $q$Quiet$q$, $q$Susan Cain$q$, 2012, $q$An exploration of how modern Western culture undervalued introverts, demonstrating how the "extrovert ideal" dominates society while underestimating the immense power and creativity of quieter minds.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004'),
  ('1400069289', $q$The Power of Habit$q$, $q$Charles Duhigg$q$, 2012, $q$An examination of habit formation science, breaking behaviors down into a Three-Step Loop (Cue, Routine, Reward) and demonstrating how identifying these patterns allows individuals and businesses to change.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004'),
  ('0316017922', $q$Outliers$q$, $q$Malcolm Gladwell$q$, 2008, $q$An analysis of what makes high-achievers unique, arguing that success isn't just about individual talent, but is deeply shaped by hidden systemic advantages, timing, culture, and upbringing.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004'),
  ('1451648537', $q$Steve Jobs$q$, $q$Walter Isaacson$q$, 2011, $q$The definitive biography based on years of exclusive interviews with the Apple co-founder, offering an unvarnished look at his intense personal drive, creative perfectionism, and technological revolution.$q$, '6c9b5e2a-0d1f-4d4f-8f01-000000000004');

UPDATE books AS b
SET
  title = s.title,
  description = s.description,
  release_date = make_date(s.release_year, 1, 1),
  category_id = s.category_id
FROM book_seed AS s
WHERE b.isbn = s.isbn;

INSERT INTO book_authors (book_id, author_id)
SELECT b.id, a.id
FROM book_seed AS s
JOIN books AS b
  ON b.isbn = s.isbn
JOIN authors AS a
  ON a.name = s.author_name
ON CONFLICT DO NOTHING;

COMMIT;