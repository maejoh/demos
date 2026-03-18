import BookShelf from "@/app/components/BookShelf"
import { fetchBooks } from "@/lib/books"

export default async function Page() {
  const { books, fetchError } = await fetchBooks()
  return <BookShelf books={books} fetchError={fetchError} />
}
