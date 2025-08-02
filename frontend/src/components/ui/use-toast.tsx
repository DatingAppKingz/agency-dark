import toast from "react-hot-toast"

export function useToast() {
  return {
    toast: (options: { title?: string; description?: string; variant?: 'default' | 'destructive' }) => {
      const message = options.title || options.description || ''
      
      if (options.variant === 'destructive') {
        toast.error(message)
      } else {
        toast.success(message)
      }
    },
    dismiss: (toastId?: string) => {
      if (toastId) {
        toast.dismiss(toastId)
      } else {
        toast.dismiss()
      }
    }
  }
}