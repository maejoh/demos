import BookShelf from "@/app/components/BookShelf"
import { fetchBooks } from "@/lib/books"

export default async function Page() {
  const books = await fetchBooks()
  return <BookShelf books={books} />
}
