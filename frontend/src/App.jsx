export default function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-white">
      <nav className="flex justify-between items-center px-8 py-5 border-b border-slate-800">
        <h1 className="text-2xl font-bold text-indigo-400">
          InterviewAce AI
        </h1>

        <button className="bg-indigo-600 px-4 py-2 rounded-lg hover:bg-indigo-500">
          Get Started
        </button>
      </nav>

      <section className="max-w-6xl mx-auto px-8 py-24 text-center">
        <h1 className="text-6xl font-bold leading-tight">
          Ace Your
          <span className="text-cyan-400"> Technical Interviews </span>
          With AI
        </h1>

        <p className="mt-6 text-xl text-slate-300">
          Upload your resume, practice interviews, and receive instant AI
          feedback to improve your placement chances.
        </p>

        <div className="mt-10 flex justify-center gap-4">
          <button className="bg-indigo-600 px-6 py-3 rounded-xl font-semibold">
            Start Interview
          </button>

          <button className="border border-slate-600 px-6 py-3 rounded-xl">
            Learn More
          </button>
        </div>
      </section>
    </div>
  )
}