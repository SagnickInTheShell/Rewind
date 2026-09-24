import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../src/App";

describe("App shell", () => {
  it("renders the top bar and upload route", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("RE")).toBeInTheDocument();
    expect(screen.getByText("WIND")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /from footage to/i })).toBeInTheDocument();
  });
});
