export type Category = "Roomies" | "Depas" | "Airbnb" | "Transporte";

export const depaFeatureOptions = [
  "Amoblado",
  "Permite mascotas",
  "Área de lavandería",
  "Balcón",
  "Terraza",
  "Ascensor",
] as const;

export type DepaFeature = typeof depaFeatureOptions[number];

export type DepaDetails = {
  delivery: string;
  availability: string;
  address: string;
  units: number;
  areaTotal: string;
  areaCovered: string;
  bedroomsMin: number;
  bedroomsMax: number;
  bathroomsMin: number;
  bathroomsMax: number;
  features: DepaFeature[];
};

export type Listing = {
  id: number;
  category: Category;
  title: string;
  location: string;
  description: string;
  image: string;
  gallery?: string[];
  price: number;
  priceLabel: string;
  rating: number;
  reviews: number;
  meta: string;
  badge?: string;
  ownerName: string;
  ownerWhatsApp: string;
  service?: string;
  details?: DepaDetails;
};

const image = (id: string) => `https://images.unsplash.com/${id}`;

export const demoListings: Listing[] = [
  {
    id: 1, category: "Roomies", title: "Habitación con luz y calma", location: "Barranco, Lima", description: "Habitación privada dentro de un depa compartido, con cocina equipada, escritorio y una comunidad tranquila.", image: image("photo-1505693416388-ac5ce068fe85"), gallery: [image("photo-1505693416388-ac5ce068fe85"), image("photo-1522708323590-d24dbb6b0267")], price: 780, priceLabel: "por mes", rating: 4.9, reviews: 18, meta: "1 cama · 1 baño compartido · Amoblado", badge: "Favorito entre roomies", ownerName: "Carla", ownerWhatsApp: "51999888777",
  },
  {
    id: 2, category: "Roomies", title: "Roomie en depa creativo", location: "Miraflores, Lima", description: "Espacio listo para mudarte, con áreas comunes amplias, buena conexión y compañeros que respetan tus tiempos.", image: image("photo-1522708323590-d24dbb6b0267"), gallery: [image("photo-1522708323590-d24dbb6b0267"), image("photo-1497366811353-6870744d04b2")], price: 920, priceLabel: "por mes", rating: 5, reviews: 12, meta: "1 cama · 1 baño · Incluye servicios", badge: "Respuesta rápida", ownerName: "Mateo", ownerWhatsApp: "51999111222",
  },
  {
    id: 3, category: "Roomies", title: "Cuarto amplio cerca al parque", location: "San Miguel, Lima", description: "Habitación espaciosa con ventana exterior, clóset y acceso a terraza compartida.", image: image("photo-1505691938895-1758d7feb511"), price: 650, priceLabel: "por mes", rating: 4.8, reviews: 9, meta: "1 cama · 1 baño compartido · Sin amoblar", ownerName: "Andrea", ownerWhatsApp: "51988777666",
  },
  {
    id: 4, category: "Roomies", title: "Habitación privada con escritorio", location: "Jesús María, Lima", description: "Ideal para estudiar o trabajar desde casa. Cocina y lavandería compartidas, edificio seguro.", image: image("photo-1524758631624-e2822e304c36"), price: 720, priceLabel: "por mes", rating: 4.9, reviews: 21, meta: "1 cama · 1 baño · Escritorio", ownerName: "Luis", ownerWhatsApp: "51987654321",
  },
  {
    id: 11, category: "Depas", title: "Edificios en Miraflores", location: "Miraflores, Lima", description: "Proyecto residencial de entrega inmediata con departamentos de uno y dos dormitorios, áreas comunes y conexión directa con el centro de Miraflores.", image: image("photo-1600607687939-ce8a6c25118c"), gallery: [image("photo-1600607687939-ce8a6c25118c"), image("photo-1600566753086-00f18fb6b3ea")], price: 2909, priceLabel: "por mes", rating: 4.9, reviews: 28, meta: "1 a 2 dormitorios · 1 a 2 baños · 53 a 60 m²", badge: "Entrega inmediata", ownerName: "Valeria", ownerWhatsApp: "51999888777", details: { delivery: "Entrega inmediata", availability: "Entrega Inmediata", address: "Av. Ricardo Palma 251, Miraflores, Lima", units: 280, areaTotal: "53 a 60 m² tot.", areaCovered: "53 a 60 m² techada", bedroomsMin: 1, bedroomsMax: 2, bathroomsMin: 1, bathroomsMax: 2, features: ["Amoblado", "Permite mascotas", "Área de lavandería", "Balcón", "Terraza", "Ascensor"] },
  },
  {
    id: 12, category: "Depas", title: "Residencial Parque Surco", location: "Santiago de Surco, Lima", description: "Departamentos contemporáneos con distribución eficiente, espacios sociales y acceso rápido a parques, colegios y comercios.", image: image("photo-1600566753190-17f0baa2a6c3"), gallery: [image("photo-1600566753190-17f0baa2a6c3"), image("photo-1600607687920-4e2a09cf159d")], price: 3100, priceLabel: "por mes", rating: 5, reviews: 15, meta: "2 a 3 dormitorios · 2 baños · 72 a 96 m²", badge: "Listo para mudarte", ownerName: "Diego", ownerWhatsApp: "51991112233", details: { delivery: "Entrega inmediata", availability: "Últimas unidades", address: "Av. Caminos del Inca 1245, Santiago de Surco, Lima", units: 64, areaTotal: "72 a 96 m² tot.", areaCovered: "68 a 90 m² techada", bedroomsMin: 2, bedroomsMax: 3, bathroomsMin: 2, bathroomsMax: 2, features: ["Amoblado", "Permite mascotas", "Área de lavandería", "Balcón", "Ascensor"] },
  },
  {
    id: 13, category: "Depas", title: "Vive frente al parque", location: "San Isidro, Lima", description: "Un edificio residencial de baja densidad con ambientes amplios, iluminación natural y seguridad permanente.", image: image("photo-1600585154340-be6161a56a0c"), price: 3600, priceLabel: "por mes", rating: 4.8, reviews: 11, meta: "3 dormitorios · 2 a 3 baños · 105 a 126 m²", ownerName: "Patricia", ownerWhatsApp: "51990001122", details: { delivery: "Disponible ahora", availability: "Contrato de 12 meses", address: "Calle Los Laureles 410, San Isidro, Lima", units: 32, areaTotal: "105 a 126 m² tot.", areaCovered: "98 a 118 m² techada", bedroomsMin: 3, bedroomsMax: 3, bathroomsMin: 2, bathroomsMax: 3, features: ["Permite mascotas", "Área de lavandería", "Balcón", "Terraza", "Ascensor"] },
  },
  {
    id: 14, category: "Depas", title: "Departamentos en Pueblo Libre", location: "Pueblo Libre, Lima", description: "Departamentos funcionales con cocina abierta, balcón y contratos desde seis meses en una zona residencial conectada.", image: image("photo-1600607687920-4e2a09cf159d"), price: 2250, priceLabel: "por mes", rating: 4.7, reviews: 8, meta: "1 a 2 dormitorios · 1 baño · 46 a 68 m²", ownerName: "Renzo", ownerWhatsApp: "51988889999", details: { delivery: "Disponible ahora", availability: "Contrato desde 6 meses", address: "Av. Brasil 1850, Pueblo Libre, Lima", units: 90, areaTotal: "46 a 68 m² tot.", areaCovered: "44 a 64 m² techada", bedroomsMin: 1, bedroomsMax: 2, bathroomsMin: 1, bathroomsMax: 1, features: ["Permite mascotas", "Área de lavandería", "Balcón", "Ascensor"] },
  },
  {
    id: 21, category: "Airbnb", title: "Departamento con diseño en Barranco", location: "Barranco, Lima", description: "Departamento con interiores cálidos, detalles locales y todo lo necesario para una escapada con personalidad.", image: image("photo-1600607687939-ce8a6c25118c"), price: 240, priceLabel: "por noche", rating: 4.98, reviews: 46, meta: "2 huéspedes · 1 habitación · Wifi", badge: "Favorito entre huéspedes", ownerName: "Sofía", ownerWhatsApp: "51999888777",
  },
  {
    id: 22, category: "Airbnb", title: "Suite luminosa cerca al malecón", location: "Miraflores, Lima", description: "Un refugio con balcón, cama king y acceso caminando al malecón y los mejores cafés.", image: image("photo-1600566753086-00f18fb6b3ea"), price: 380, priceLabel: "por noche", rating: 4.96, reviews: 32, meta: "2 huéspedes · 1 habitación · Vista al mar", badge: "Reserva flexible", ownerName: "Camila", ownerWhatsApp: "51992223344",
  },
  {
    id: 23, category: "Airbnb", title: "Casa tranquila para desconectar", location: "Cieneguilla, Lima", description: "Casa rodeada de verde para bajar el ritmo, leer y compartir una estadía diferente.", image: image("photo-1600585154340-be6161a56a0c"), price: 420, priceLabel: "por noche", rating: 4.9, reviews: 19, meta: "4 huéspedes · 2 habitaciones · Piscina", ownerName: "Nicolás", ownerWhatsApp: "51995556677",
  },
  {
    id: 24, category: "Airbnb", title: "Mini depa con diseño local", location: "Centro de Lima", description: "Un espacio compacto, bonito y funcional para conocer la ciudad desde el corazón.", image: image("photo-1600566753190-17f0baa2a6c3"), price: 190, priceLabel: "por noche", rating: 4.85, reviews: 27, meta: "2 huéspedes · 1 habitación · Cocina", ownerName: "Mariana", ownerWhatsApp: "51991119911",
  },
  {
    id: 31, category: "Transporte", title: "Mudanza segura para tu depa", location: "Lima Metropolitana", description: "Equipo puntual para mudanzas de hogar, oficina o habitación. Cuidamos cada caja y coordinamos por WhatsApp.", image: image("photo-1601584115197-04ecc0da31d8"), price: 180, priceLabel: "por servicio", rating: 4.9, reviews: 36, meta: "Camión 3 t · 12 m³ · 2 ayudantes", badge: "Más solicitado", ownerName: "Mudanzas Norte", ownerWhatsApp: "51999911111", service: "Mudanza",
  },
  {
    id: 32, category: "Transporte", title: "Furgón para mudanzas medianas", location: "Lima y Callao", description: "Furgón cerrado para traslados de hasta 1.5 toneladas, con seguimiento y carga protegida.", image: image("photo-1586864387967-d02ef85d93e8"), price: 140, priceLabel: "por servicio", rating: 4.8, reviews: 22, meta: "Furgón 1.5 t · 8 m³ · Carga protegida", ownerName: "Ruta 24", ownerWhatsApp: "51998881122", service: "Mudanza",
  },
  {
    id: 33, category: "Transporte", title: "SUV premium para corporativo", location: "Lima Metropolitana", description: "Traslados corporativos en camioneta premium 2026, conductor profesional y vehículo verificado.", image: image("photo-1549317661-bd32c8ce0db2"), price: 260, priceLabel: "por servicio", rating: 5, reviews: 17, meta: "SUV premium 2026 · 4 pasajeros · Verificado", badge: "Vehículo verificado", ownerName: "Elite Drive", ownerWhatsApp: "51997776655", service: "Corporativo",
  },
  {
    id: 34, category: "Transporte", title: "Camioneta ejecutiva 2025", location: "Lima · Aeropuerto · Eventos", description: "Servicio premium para reuniones, aeropuerto y eventos. Reserva por horas o por jornada.", image: image("photo-1551830820-330a71b99659"), price: 310, priceLabel: "por servicio", rating: 4.95, reviews: 14, meta: "Camioneta 2025 · 6 pasajeros · Verificado", ownerName: "Prime Mobility", ownerWhatsApp: "51996665544", service: "Corporativo",
  },
];
