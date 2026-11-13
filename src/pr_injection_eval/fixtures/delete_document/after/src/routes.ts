import { Router } from "express";
import { requireLogin } from "./auth";
import { deleteDocument, getDocument } from "./documents";

export const router = Router();

router.use(requireLogin);
router.get("/documents/:id", getDocument);
router.delete("/documents/:id", deleteDocument);
