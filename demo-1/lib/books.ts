export type Book = {
  id: string
  title: string
  author: string
  tags: string[]
  votes: number
}

// TODO: replace with Redis fetch
export const mockBooks: Book[] = [
  {
    id: "1",
    title: "You Don't Know JS: Scope & Closures",
    author: "Kyle Simpson",
    tags: ["JavaScript"],
    votes: 0,
  },
  {
    id: "2",
    title: "Programming TypeScript",
    author: "Boris Cherny",
    tags: ["TypeScript"],
    votes: 0,
  },
  {
    id: "3",
    title: "Learning React",
    author: "Alex Banks & Eve Porcello",
    tags: ["React", "JavaScript"],
    votes: 0,
  },
  {
    id: "4",
    title: "Designing Data-Intensive Applications",
    author: "Martin Kleppmann",
    tags: ["Databases", "Systems Design"],
    votes: 0,
  },
  {
    id: "5",
    title: "The Pragmatic Programmer",
    author: "David Thomas & Andrew Hunt",
    tags: ["Software Engineering"],
    votes: 0,
  },
  {
    id: "6",
    title: "Learning SQL",
    author: "Alan Beaulieu",
    tags: ["SQL", "Databases"],
    votes: 0,
  },
  {
    id: "7",
    title: "A Philosophy of Software Design",
    author: "John Ousterhout",
    tags: ["Software Engineering", "Software Architecture"],
    votes: 0,
  },
  {
    id: "8",
    title: "Discrete Mathematics and Its Applications",
    author: "Kenneth Rosen",
    tags: ["Computer Science", "Mathematics"],
    votes: 0,
  },
]
