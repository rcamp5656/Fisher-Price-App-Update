import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Splash from "./components/Splash";
import "@/App.css";
import Creator from "@/pages/Creator";
import Shared from "@/pages/Shared";
import { Toaster } from "@/components/ui/sonner";

function App() {
  return (
    <BrowserRouter>
      <Splash />
      <Routes>
        <Route path="/" element={<Creator />} />
        <Route path="/r/:id" element={<Shared />} />
      </Routes>
      <Toaster position="bottom-center" richColors />
    </BrowserRouter>
  );
}

export default App;
