import { Router } from "express";
import { requireLogin } from "./auth";
import { getDocument } from "./documents";

export const router = Router();

router.use(requireLogin);
router.get("/documents/:id", getDocument);
