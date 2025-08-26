-- Create admins table for admin management
CREATE TABLE IF NOT EXISTS admins (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    role TEXT DEFAULT 'admin',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create medicines table (admin-controlled) with proper image references
CREATE TABLE IF NOT EXISTS medicines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    benefits TEXT,
    contraindications TEXT,
    description TEXT,
    price TEXT,
    photo TEXT, -- Telegram file ID (fallback)
    medicine_image_id UUID REFERENCES images(id), -- Supabase Storage reference
    is_active BOOLEAN DEFAULT true,
    added_by_admin BIGINT REFERENCES admins(user_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create image storage table for Supabase Storage integration
CREATE TABLE IF NOT EXISTS images (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    mime_type TEXT,
    telegram_file_id TEXT,
    supabase_url TEXT,
    uploaded_by BIGINT,
    image_type TEXT CHECK (image_type IN ('medicine_photo', 'receipt_photo', 'profile_photo')),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create orders table with proper image references
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username TEXT,
    full_name TEXT,
    medicine TEXT NOT NULL,
    months INTEGER DEFAULT 1,
    price TEXT,
    status TEXT DEFAULT 'new',
    delivery_region TEXT,
    delivery_district TEXT,
    delivery_address TEXT,
    phone_number TEXT,
    receipt_photo_id TEXT, -- Telegram file ID (fallback)
    receipt_image_id UUID REFERENCES images(id), -- Supabase Storage reference
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default admin (replace with your admin user ID)
INSERT INTO admins (user_id, username, full_name, role) VALUES
(5747916482, 'admin', 'Bot Admin', 'super_admin')
ON CONFLICT (user_id) DO NOTHING;

-- No default medicines - only admins can add them through the bot interface
