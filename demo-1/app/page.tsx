import BookShelf from "@/app/components/BookShelf"
import { mockBooks } from "@/lib/books"

export default function Page() {
  return <BookShelf books={mockBooks} />
}
